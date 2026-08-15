"""Servicio de aplicacion. Orquesta Extractor + Procesador NLP + DB.

Concentra las reglas transversales del sistema:
- CU-02 -> CU-12: pipeline completo de consulta
- RF-13.2: derivacion del perfil desde el historial del usuario
- RF-14.5: reutilizacion de la ultima explicacion
- RF-10.1: historial en sesion
- Metodologia de evaluacion: activacion de la encuesta al llegar al umbral.
"""

from __future__ import annotations

import logging
from collections import Counter

from extractor import (
    BancoCentralExtractor,
    CacheIndicadores,
    IPSA_TICKERS,
    RANGOS_TEMPORALES,
    Trazabilidad,
    YahooExtractor,
)
from extractor.normalizer import IndicadorNormalizado
from nlp_processor import (
    Explicacion,
    GeneradorExplicaciones,
    PerfilAprendizaje,
    clasificar_riesgo,
)

from .extensions import db
from .models import Consulta, ExplicacionCache, Regeneracion, Usuario

_LOG = logging.getLogger("app.services")

_indicadores_soportados = ("rsi", "volatilidad", "media_movil", "rentabilidad")


class ServicioConsulta:
    """Punto unico de entrada para las vistas del Presentador."""

    def __init__(
        self,
        yahoo: YahooExtractor | None = None,
        banco_central: BancoCentralExtractor | None = None,
        generador: GeneradorExplicaciones | None = None,
    ) -> None:
        cache = CacheIndicadores()
        trazabilidad = Trazabilidad()
        self.yahoo = yahoo or YahooExtractor(cache=cache, trazabilidad=trazabilidad)
        self.banco_central = banco_central or BancoCentralExtractor(
            cache=cache, trazabilidad=trazabilidad
        )
        self.generador = generador or GeneradorExplicaciones()

    # ------------------------------------------------------------------
    # Datos publicos
    # ------------------------------------------------------------------
    @property
    def tickers(self) -> dict[str, str]:
        return IPSA_TICKERS

    @property
    def rangos(self) -> list[str]:
        return list(RANGOS_TEMPORALES)

    @property
    def indicadores(self) -> tuple[str, ...]:
        return _indicadores_soportados

    def cinta_precios(self) -> dict:
        """Datos consumidos por la cinta (CU-17)."""

        bundle = self.banco_central.extraer()
        return {
            "macro": bundle.valores,
            "fecha": bundle.fecha_extraccion,
        }

    # ------------------------------------------------------------------
    # Pipeline de consulta
    # ------------------------------------------------------------------
    def consultar(
        self,
        usuario: Usuario,
        ticker: str,
        indicador: str,
        rango: str,
    ) -> tuple[Explicacion, IndicadorNormalizado]:
        if indicador not in self.indicadores:
            raise ValueError(f"Indicador '{indicador}' no soportado.")

        datos = self.yahoo.extraer(ticker, rango)
        perfil = self._perfil_de(usuario)
        explicacion = self.generador.generar(indicador, datos, perfil)

        self._persistir_consulta(usuario, ticker, indicador, rango, explicacion, datos)
        self._cachear_explicacion(usuario, ticker, indicador, explicacion)
        return explicacion, datos

    def regenerar(
        self,
        usuario: Usuario,
        consulta_id: int,
    ) -> Explicacion:
        consulta = Consulta.query.filter_by(id=consulta_id, usuario_id=usuario.id).first()
        if consulta is None:
            raise ValueError("Consulta no encontrada para este usuario.")

        datos = self.yahoo.extraer(consulta.ticker, consulta.rango)
        perfil = self._perfil_de(usuario)
        previos = Regeneracion.query.filter_by(consulta_id=consulta.id).count()
        explicacion = self.generador.regenerar(
            consulta.indicador, datos, perfil, intento_previo=previos
        )

        db.session.add(Regeneracion(consulta_id=consulta.id))
        db.session.commit()
        self._cachear_explicacion(usuario, consulta.ticker, consulta.indicador, explicacion)
        return explicacion

    # ------------------------------------------------------------------
    # Perfil y resumen
    # ------------------------------------------------------------------
    def resumen_perfil(self, usuario: Usuario) -> dict:
        consultas = Consulta.query.filter_by(usuario_id=usuario.id).all()
        total = len(consultas)

        regeneraciones_por_indicador: Counter[str] = Counter()
        for consulta in consultas:
            regs = Regeneracion.query.filter_by(consulta_id=consulta.id).count()
            if regs:
                regeneraciones_por_indicador[consulta.indicador] += regs

        instrumentos = Counter(c.ticker for c in consultas).most_common(5)
        indicador_dificil = (
            regeneraciones_por_indicador.most_common(1)[0][0]
            if regeneraciones_por_indicador
            else None
        )

        explicacion_dificil = None
        datos_dificil = None
        if indicador_dificil:
            explicacion_dificil, datos_dificil = self._explicacion_dificil(usuario, indicador_dificil)

        return {
            "total_consultas": total,
            "instrumentos_mas_consultados": instrumentos,
            "indicador_mas_regenerado": indicador_dificil,
            "explicacion_dificil": explicacion_dificil,
            "datos_dificil": datos_dificil,
            "perfil": self._perfil_de(usuario),
            "ofrecer_encuesta": (
                usuario.consentimiento_eval
                and not usuario.encuesta_ofrecida
                and total >= 5
            ),
        }

    # ------------------------------------------------------------------
    # Helpers privados
    # ------------------------------------------------------------------
    def _perfil_de(self, usuario: Usuario) -> PerfilAprendizaje:
        total = Consulta.query.filter_by(usuario_id=usuario.id).count()
        regens = (
            db.session.query(Regeneracion)
            .join(Consulta, Consulta.id == Regeneracion.consulta_id)
            .filter(Consulta.usuario_id == usuario.id)
            .count()
        )
        return PerfilAprendizaje.desde_actividad(total, regens)

    def _persistir_consulta(
        self,
        usuario: Usuario,
        ticker: str,
        indicador: str,
        rango: str,
        explicacion: Explicacion,
        datos: IndicadorNormalizado,
    ) -> None:
        consulta = Consulta(
            usuario_id=usuario.id,
            ticker=ticker,
            indicador=indicador,
            rango=rango,
            valor=explicacion.valor,
            riesgo=explicacion.riesgo.nivel,
        )
        db.session.add(consulta)
        db.session.commit()
        explicacion.metadata["consulta_id"] = str(consulta.id)

    def _cachear_explicacion(
        self,
        usuario: Usuario,
        ticker: str,
        indicador: str,
        explicacion: Explicacion,
    ) -> None:
        existente = ExplicacionCache.query.filter_by(
            usuario_id=usuario.id, ticker=ticker, indicador=indicador
        ).first()
        if existente:
            existente.texto = explicacion.texto
            existente.valor = explicacion.valor
            existente.riesgo = explicacion.riesgo.nivel
        else:
            db.session.add(
                ExplicacionCache(
                    usuario_id=usuario.id,
                    ticker=ticker,
                    indicador=indicador,
                    texto=explicacion.texto,
                    valor=explicacion.valor,
                    riesgo=explicacion.riesgo.nivel,
                )
            )
        db.session.commit()

    def _explicacion_dificil(
        self, usuario: Usuario, indicador: str
    ) -> tuple[Explicacion | None, IndicadorNormalizado | None]:
        # RF-14.5: preferir la ultima explicacion cacheada.
        cacheada = (
            ExplicacionCache.query.filter_by(usuario_id=usuario.id, indicador=indicador)
            .order_by(ExplicacionCache.generada_en.desc())
            .first()
        )
        if cacheada is None:
            return None, None
        etiqueta = clasificar_riesgo(0.0)  # placeholder cuando solo tenemos cache
        etiqueta.nivel = cacheada.riesgo  # type: ignore[misc]
        # Reconstruimos un Explicacion minimo desde el cache; el sentimiento
        # queda como heuristica neutral para no llamar al modelo aca.
        from nlp_processor.finbert import ResultadoFinBert
        exp = Explicacion(
            indicador=indicador,  # type: ignore[arg-type]
            valor=cacheada.valor,
            texto=cacheada.texto,
            riesgo=etiqueta,
            finbert=ResultadoFinBert("neutral", 0.5, "cache"),
            perfil_usado=self._perfil_de(usuario).nivel_detalle,
            origen="cache",
        )
        return exp, None
