"""Generacion de explicaciones comprensibles (RF-05, RF-06.2).

- RF-05.1: cada explicacion evita jerga sin definirla en el mismo texto.
- RF-05.2: adapta el nivel de detalle al perfil no experto.
- RF-06.2: soporta regeneracion (nueva redaccion) por peticion del usuario.

El generador usa plantillas parametrizadas por indicador y perfil, y
enriquece la explicacion con el sentimiento del FinBertProcessor
(RF-04.1) cuando el modelo esta disponible.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Literal

from extractor.normalizer import IndicadorNormalizado

from .finbert import FinBertProcessor, ResultadoFinBert
from .risk import Etiqueta, clasificar_riesgo
from .validator import CoherenciaError, categoria_rsi, validar_coherencia

NombreIndicador = Literal["rsi", "volatilidad", "media_movil", "rentabilidad"]
NivelDetalle = Literal["basico", "intermedio", "avanzado"]


@dataclass
class PerfilAprendizaje:
    """Perfil derivado del historial del usuario.

    - `nivel_detalle`: se computa a partir del numero de consultas y
      regeneraciones. Un usuario nuevo comienza en 'basico' y sube al
      mostrar suficiente actividad sin regeneraciones (RF-13.2).
    """

    nivel_detalle: NivelDetalle = "basico"
    consultas: int = 0
    regeneraciones: int = 0

    @classmethod
    def desde_actividad(cls, consultas: int, regeneraciones: int) -> "PerfilAprendizaje":
        nivel: NivelDetalle = "basico"
        if consultas >= 10 and regeneraciones <= consultas * 0.2:
            nivel = "intermedio"
        if consultas >= 25 and regeneraciones <= consultas * 0.1:
            nivel = "avanzado"
        return cls(
            nivel_detalle=nivel,
            consultas=consultas,
            regeneraciones=regeneraciones,
        )


@dataclass
class Explicacion:
    """Salida final del Procesador NLP para un indicador consultado."""

    indicador: NombreIndicador
    valor: float
    texto: str
    riesgo: Etiqueta
    finbert: ResultadoFinBert
    perfil_usado: NivelDetalle
    reintentos: int = 0
    origen: str = "generado"  # "generado" | "cache"
    metadata: dict[str, str] = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "indicador": self.indicador,
            "valor": self.valor,
            "texto": self.texto,
            "riesgo": {
                "nivel": self.riesgo.nivel,
                "color": self.riesgo.color,
                "icono": self.riesgo.icono,
            },
            "finbert": {
                "sentimiento": self.finbert.sentimiento,
                "score": self.finbert.score,
                "fuente": self.finbert.fuente,
            },
            "perfil_usado": self.perfil_usado,
            "reintentos": self.reintentos,
            "origen": self.origen,
            "metadata": self.metadata,
        }


class GeneradorExplicaciones:
    """Redacta explicaciones y las adapta al perfil (RF-05, RF-06)."""

    LIMITE_PALABRAS = 150  # RNF-04.2

    def __init__(self, finbert: FinBertProcessor | None = None) -> None:
        self.finbert = finbert or FinBertProcessor()

    # ------------------------------------------------------------------
    # API publica
    # ------------------------------------------------------------------
    def generar(
        self,
        indicador: NombreIndicador,
        datos: IndicadorNormalizado,
        perfil: PerfilAprendizaje | None = None,
        variante: int = 0,
    ) -> Explicacion:
        """Genera una explicacion valida para el indicador solicitado."""

        perfil = perfil or PerfilAprendizaje()
        valor = self._extraer_valor(indicador, datos)
        sentimiento = self.finbert.procesar(
            texto=f"{indicador} {valor} {datos.ticker}",
            valor_referencia=valor if indicador != "rsi" else valor - 50,
        )

        etiqueta = clasificar_riesgo(datos.volatilidad, datos.rsi)

        reintentos = 0
        texto = self._redactar(indicador, valor, datos, perfil, sentimiento, variante)
        for intento in range(3):
            try:
                validar_coherencia(indicador, valor, texto)
                break
            except CoherenciaError:
                reintentos = intento + 1
                texto = self._redactar(
                    indicador, valor, datos, perfil, sentimiento, variante + reintentos + 1
                )
        texto = self._recortar(texto)

        return Explicacion(
            indicador=indicador,
            valor=valor,
            texto=texto,
            riesgo=etiqueta,
            finbert=sentimiento,
            perfil_usado=perfil.nivel_detalle,
            reintentos=reintentos,
            metadata={
                "ticker": datos.ticker,
                "rango": datos.rango,
                "empresa": datos.metadata.get("nombre_empresa", ""),
            },
        )

    def regenerar(
        self,
        indicador: NombreIndicador,
        datos: IndicadorNormalizado,
        perfil: PerfilAprendizaje | None = None,
        intento_previo: int = 0,
    ) -> Explicacion:
        """RF-06.2: entrega una version alternativa del texto."""

        return self.generar(indicador, datos, perfil, variante=intento_previo + 1)

    # ------------------------------------------------------------------
    # Redaccion por indicador
    # ------------------------------------------------------------------
    def _redactar(
        self,
        indicador: str,
        valor: float,
        datos: IndicadorNormalizado,
        perfil: PerfilAprendizaje,
        sentimiento: ResultadoFinBert,
        variante: int,
    ) -> str:
        empresa = datos.metadata.get("nombre_empresa") or datos.ticker
        detalle = perfil.nivel_detalle

        if indicador == "rsi":
            return self._rsi(empresa, valor, detalle, variante)
        if indicador == "volatilidad":
            return self._volatilidad(empresa, valor, detalle, variante)
        if indicador == "media_movil":
            return self._media(empresa, datos, detalle, variante)
        if indicador == "rentabilidad":
            return self._rentabilidad(empresa, valor, datos.rango, detalle, sentimiento, variante)
        raise ValueError(f"Indicador '{indicador}' no soportado por el generador.")

    def _rsi(self, empresa: str, valor: float, detalle: str, variante: int) -> str:
        cat = categoria_rsi(valor)
        base_basico = [
            (
                f"El RSI (Indice de Fuerza Relativa, un numero entre 0 y 100) "
                f"de {empresa} es {valor:.1f}. Eso significa que hoy la accion "
                f"esta en zona '{cat}'."
            ),
            (
                f"Para {empresa} el RSI marca {valor:.1f}. El RSI es un numero "
                f"entre 0 y 100 que muestra cuanto ha subido o bajado la accion "
                f"ultimamente. En este momento se encuentra en zona '{cat}'."
            ),
        ]
        cierre = {
            "sobrecomprado": (
                " Esto quiere decir que subio bastante rapido y algunos "
                "inversionistas creen que podria bajar en el corto plazo."
            ),
            "sobrevendido": (
                " Esto quiere decir que bajo bastante rapido y algunos "
                "inversionistas creen que podria recuperarse en el corto plazo."
            ),
            "neutral": (
                " Esto quiere decir que la accion no muestra movimientos "
                "extremos hacia arriba ni hacia abajo."
            ),
        }[cat]
        elegido = base_basico[variante % len(base_basico)]
        if detalle == "basico":
            return elegido + cierre
        extra = (
            " En terminos tecnicos, valores sobre 70 se consideran sobrecomprado, "
            "y bajo 30 sobrevendido. El resto se ve como zona neutral."
        )
        if detalle == "intermedio":
            return elegido + cierre + extra
        avanzado = (
            f" Este calculo usa una ventana de 14 dias y compara las ganancias "
            f"promedio con las perdidas promedio del periodo."
        )
        return elegido + cierre + extra + avanzado

    def _volatilidad(self, empresa: str, valor: float, detalle: str, variante: int) -> str:
        if valor < 15:
            resumen = "es baja, es decir que su precio se mueve de forma tranquila."
        elif valor < 30:
            resumen = "es moderada, sube y baja de manera notoria pero sin sobresaltos grandes."
        else:
            resumen = "es alta, es decir que su precio puede cambiar bastante en poco tiempo."
        variantes = [
            (
                f"La volatilidad (cuanto se mueve el precio) de {empresa} es "
                f"{valor:.1f}% anual. {resumen.capitalize()}"
            ),
            (
                f"En {empresa} la volatilidad anualizada llega a {valor:.1f}%. "
                f"La volatilidad mide que tanto cambia el precio, y aca {resumen}"
            ),
        ]
        base = variantes[variante % len(variantes)]
        if detalle == "basico":
            return base
        return (
            base
            + " Una volatilidad mas alta suele estar asociada a un mayor riesgo, "
            "porque el precio puede alejarse rapido de lo esperado."
        )

    def _media(self, empresa: str, datos: IndicadorNormalizado, detalle: str, variante: int) -> str:
        corta = datos.media_movil_corta
        larga = datos.media_movil_larga
        tendencia = "al alza" if corta > larga else "a la baja"
        variantes = [
            (
                f"La media movil corta (promedio de los ultimos 20 dias) de "
                f"{empresa} vale {corta:.2f}, y la larga (50 dias) vale "
                f"{larga:.2f}. Como la corta esta {'por encima' if corta > larga else 'por debajo'} "
                f"de la larga, la tendencia reciente es {tendencia}."
            ),
            (
                f"Para {empresa}, el promedio de precios de los ultimos 20 dias "
                f"({corta:.2f}) esta {'sobre' if corta > larga else 'bajo'} el "
                f"promedio de 50 dias ({larga:.2f}). Esto muestra una tendencia "
                f"{tendencia}."
            ),
        ]
        base = variantes[variante % len(variantes)]
        if detalle == "basico":
            return base
        return (
            base
            + " Las medias moviles alisan el 'ruido' del dia a dia y ayudan a ver "
            "hacia donde va la accion en el mediano plazo."
        )

    def _rentabilidad(
        self,
        empresa: str,
        valor: float,
        rango: str,
        detalle: str,
        sentimiento: ResultadoFinBert,
        variante: int,
    ) -> str:
        signo = "gano" if valor > 0 else "perdio"
        variantes = [
            (
                f"Durante los ultimos {rango}, {empresa} {signo} {abs(valor):.2f}% "
                f"de valor. Es la rentabilidad, es decir, cuanto habrias ganado o "
                f"perdido por cada 100 pesos invertidos."
            ),
            (
                f"En los ultimos {rango}, {empresa} tuvo una rentabilidad de "
                f"{valor:.2f}%. Esa cifra indica cuanto {signo} la accion respecto "
                f"al precio del inicio del periodo."
            ),
        ]
        base = variantes[variante % len(variantes)]
        if detalle == "basico":
            return base
        return (
            base
            + f" Segun el analisis de sentimiento del modelo, la percepcion "
            f"general es {sentimiento.sentimiento}."
        )

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------
    def _extraer_valor(self, indicador: str, datos: IndicadorNormalizado) -> float:
        return {
            "rsi": datos.rsi,
            "volatilidad": datos.volatilidad,
            "media_movil": datos.media_movil_corta,
            "rentabilidad": datos.rentabilidad,
        }[indicador]

    def _recortar(self, texto: str) -> str:
        palabras = texto.split()
        if len(palabras) <= self.LIMITE_PALABRAS:
            return texto
        return " ".join(palabras[: self.LIMITE_PALABRAS]) + "..."
