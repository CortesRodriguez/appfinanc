"""Glosario simplificado de terminos financieros (RF-09.2)."""

from __future__ import annotations

GLOSARIO: dict[str, str] = {
    "rsi": (
        "Indice de Fuerza Relativa. Es un numero entre 0 y 100 que muestra "
        "si una accion ha subido o bajado mucho en poco tiempo. Sobre 70 "
        "suele considerarse 'sobrecomprado' (podria bajar), bajo 30 "
        "'sobrevendido' (podria subir)."
    ),
    "volatilidad": (
        "Mide cuanto se mueven los precios de una accion. Una volatilidad "
        "alta significa que el precio cambia rapido y de forma marcada, "
        "por lo que la inversion es mas riesgosa."
    ),
    "media movil": (
        "Es el promedio del precio de una accion durante una cantidad "
        "de dias. Ayuda a ver la tendencia sin el 'ruido' de los cambios "
        "diarios."
    ),
    "rentabilidad": (
        "Es el porcentaje que ganaste o perdiste con una inversion durante "
        "un periodo. Se calcula comparando el precio inicial con el precio "
        "final."
    ),
    "ipsa": (
        "Indice que agrupa las 30 acciones mas importantes de la Bolsa de "
        "Santiago. Sirve como termometro general de la bolsa chilena."
    ),
    "uf": (
        "Unidad de Fomento. Es un valor en pesos que se actualiza cada dia "
        "segun la inflacion. Se usa en creditos hipotecarios y algunas "
        "inversiones."
    ),
    "tpm": (
        "Tasa de Politica Monetaria. Es la tasa de interes que fija el "
        "Banco Central. Cuando sube, los creditos se vuelven mas caros y "
        "los depositos a plazo pagan mas."
    ),
    "ipc": (
        "Indice de Precios al Consumidor. Mide cuanto suben (o bajan) en "
        "promedio los precios de los productos y servicios que compran las "
        "familias."
    ),
    "dolar observado": (
        "Es el precio promedio del dolar del dia anterior en el mercado "
        "chileno. Se usa como referencia oficial."
    ),
    "sobrecomprado": (
        "Situacion en que una accion ha subido demasiado rapido. Suele "
        "aparecer cuando el RSI supera 70 y puede indicar una posible "
        "correccion a la baja."
    ),
    "sobrevendido": (
        "Situacion en que una accion ha bajado demasiado rapido. Suele "
        "aparecer cuando el RSI cae bajo 30 y puede indicar una posible "
        "recuperacion."
    ),
}


def buscar_termino(consulta: str) -> list[tuple[str, str]]:
    """Busqueda simple case-insensitive sobre las claves del glosario."""

    consulta = consulta.strip().lower()
    if not consulta:
        return list(GLOSARIO.items())
    return [(k, v) for k, v in GLOSARIO.items() if consulta in k]
