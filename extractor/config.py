"""Configuracion del Modulo Extractor.

RF-01.1: listado predefinido de las 30 empresas del IPSA y rangos
temporales soportados por la interfaz de consulta.
Los rangos numericos validos por indicador (RF-03.2) tambien viven aca
para mantener una unica fuente de verdad.
"""

from __future__ import annotations

# RF-01.1: 30 empresas del IPSA. Se utiliza el ticker de Yahoo Finance
# (sufijo .SN para acciones chilenas). El nombre es informativo y se
# muestra al usuario en la interfaz de seleccion.
IPSA_TICKERS: dict[str, str] = {
    "AGUAS-A.SN": "Aguas Andinas",
    "ANDINA-B.SN": "Embotelladora Andina",
    "BCI.SN": "Banco de Credito e Inversiones",
    "BSANTANDER.SN": "Banco Santander Chile",
    "CAP.SN": "CAP",
    "CCU.SN": "Compañia Cervecerias Unidas",
    "CENCOSHOPP.SN": "Cencosud Shopping",
    "CENCOSUD.SN": "Cencosud",
    "CHILE.SN": "Banco de Chile",
    "CMPC.SN": "Empresas CMPC",
    "COLBUN.SN": "Colbun",
    "CONCHATORO.SN": "Viña Concha y Toro",
    "COPEC.SN": "Empresas Copec",
    "ECL.SN": "Engie Energia Chile",
    "ENELAM.SN": "Enel Americas",
    "ENELCHILE.SN": "Enel Chile",
    "ENTEL.SN": "Entel",
    "FALABELLA.SN": "Falabella",
    "IAM.SN": "Inversiones Aguas Metropolitanas",
    "ITAUCL.SN": "Itau Chile",
    "LTM.SN": "Latam Airlines",
    "MALLPLAZA.SN": "Mall Plaza",
    "ORO BLANCO.SN": "Oro Blanco",
    "PARAUCO.SN": "Parque Arauco",
    "QUINENCO.SN": "Quiñenco",
    "RIPLEY.SN": "Ripley Corp",
    "SMSAAM.SN": "SM SAAM",
    "SONDA.SN": "Sonda",
    "SQM-B.SN": "Sociedad Quimica y Minera",
    "VAPORES.SN": "Compañia Sud Americana de Vapores",
}

# RF-01.1: rangos temporales que puede seleccionar el usuario. El valor
# es la cadena que espera Yahoo Finance en el parametro `period`.
RANGOS_TEMPORALES: dict[str, str] = {
    "1 mes": "1mo",
    "3 meses": "3mo",
    "6 meses": "6mo",
    "1 año": "1y",
}

# RF-03.2: rangos numericos aceptables por indicador. Cualquier valor
# fuera de estos limites es descartado por el validator antes de pasar
# al Procesador NLP (Sprint 6).
RANGOS_VALIDOS: dict[str, tuple[float, float]] = {
    "rsi": (0.0, 100.0),
    "volatilidad": (0.0, 500.0),        # % anualizado
    "media_movil": (0.0, 1_000_000.0),  # precio en CLP
    "rentabilidad": (-100.0, 1000.0),   # % en el periodo
    "precio": (0.0, 1_000_000.0),
}

# RF-04.2 (nota, no implementado aun): umbrales cualitativos del RSI.
# Se declaran aca desde ya para que el Procesador NLP los consuma sin
# duplicar constantes.
UMBRALES_RSI: dict[str, tuple[float, float]] = {
    "sobrevendido": (0.0, 30.0),
    "neutral": (30.0, 70.0),
    "sobrecomprado": (70.0, 100.0),
}

# RNF-02.2: intervalo (segundos) durante el cual el cache mantiene un
# indicador vigente antes de volver a consultar la API.
CACHE_TTL_SEG: int = 5 * 60

# RNF-09.2: reintentos automaticos ante fallas de conexion con APIs
# externas antes de reportar el error al usuario.
REINTENTOS_MAX: int = 3
REINTENTO_ESPERA_SEG: float = 1.5
