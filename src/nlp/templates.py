"""Plantillas de respaldo por nivel (RF-05, RF-13.2).

`TEMPLATES[nivel][indicador][riesgo]` es una lista de 3 redacciones ORDENADAS POR ESTILO
(indice = `variant`), igual en los 3 niveles, 4 indicadores y 3 niveles de riesgo. El perfil
aprende en cual se detiene el usuario (profile.service.preferred_variant) y la usa como
punto de partida.

  0 directa:        el dato primero, frases cortas.
  1 conversacional: tono cercano.
  2 con contexto:   basico -> que suele pasar despues; intermedio -> que mide el indicador;
                    avanzado -> que vigilar a continuacion.

Cada nivel sigue la ficha de `levels.LEVELS` (vocabulario, umbrales, extension). Los
marcadores disponibles (ver `explainer._fill_template`) son:
  {symbol} {value} {risk_label} {trend}
  {zona}  lectura tecnica con el umbral ("en sobrecompra (sobre 70)")  -> intermedio / avanzado
  {llano} lectura en lenguaje cotidiano ("subio muy rapido")             -> basico
  {dir}   "hacia arriba" / "hacia abajo"                                 -> basico
Las plantillas "alto" no afirman sobrecompra ni sobreventa por su cuenta: eso lo aporta
{zona}/{llano} segun la senal real, para no contradecir al validador de coherencia.
"""

STYLE_LABELS = {0: "directa", 1: "conversacional", 2: "con contexto"}

# Una frase de contexto del mercado chileno para basico e intermedio (el avanzado no la lleva).
NATIONAL_REFERENCES = {
    "rsi": ["Conviene mirarlo junto al IPSA, para no sacar conclusiones con una sola acción."],
    "medias_moviles": ["Compáralo con el IPSA: así ves si es propio de la acción o de todo el mercado chileno."],
    "macd": ["Revisa también el IPSA en las mismas fechas: sirve para saber si el impulso es propio o de todo el mercado."],
    "bandas_bollinger": ["Contrástalo con el IPSA en las mismas fechas, pues el mercado chileno tiene poco volumen."],
}

_BASICO = {
    "rsi": {
        "bajo": [
            "El RSI de {symbol} es {value} puntos ({risk_label}). Compara cuánto subió y cuánto bajó el precio en las últimas semanas; hoy se ha movido con calma, sin exceso.",
            "El RSI de {symbol} marca {value} puntos ({risk_label}), en una escala de 0 a 100 que compara las subidas con las bajadas recientes. El precio se ha movido con calma, nada fuera de lo común.",
            "El RSI compara cuánto subió y cuánto bajó el precio en las últimas semanas. {symbol} marca {value} puntos ({risk_label}): el precio se ha movido con calma, y en estos casos no suele haber un cambio brusco cerca.",
        ],
        "medio": [
            "El RSI de {symbol} es {value} puntos ({risk_label}). Compara cuánto subió y cuánto bajó el precio en las últimas semanas; aquí está a mitad de camino, sin señal clara.",
            "El RSI de {symbol} marca {value} puntos ({risk_label}), en una escala de 0 a 100 que compara las subidas con las bajadas recientes. Está a mitad de camino, así que conviene esperar más señales.",
            "El RSI compara cuánto subió y cuánto bajó el precio en las últimas semanas, de 0 a 100. {symbol} marca {value} puntos ({risk_label}): ni subió ni bajó de forma exagerada, por lo que todavía no hay una señal contundente.",
        ],
        "alto": [
            "El RSI de {symbol} es {value} puntos ({risk_label}). Compara cuánto subió y cuánto bajó el precio en las últimas semanas: el precio {llano}, y eso suele ir seguido de una pausa o un cambio.",
            "El RSI de {symbol} marca {value} puntos ({risk_label}), en una escala de 0 a 100 que compara las subidas con las bajadas recientes. El precio {llano}; después de algo así suele frenar o cambiar de rumbo.",
            "El RSI compara cuánto subió y cuánto bajó el precio en las últimas semanas. {symbol} marca {value} puntos ({risk_label}): el precio {llano}. Cuando se mueve así de rápido, es común que luego frene o cambie de rumbo.",
        ],
    },
    "medias_moviles": {
        "bajo": [
            "Las medias móviles de {symbol} muestran que el precio va {dir}: {value}% de diferencia entre el promedio de los últimos días y el de semanas atrás ({risk_label}). Es un movimiento moderado.",
            "Si comparas el precio promedio reciente de {symbol} con el de semanas atrás, el precio va {dir}: {value}% de diferencia ({risk_label}). Un movimiento moderado.",
            "Las medias móviles muestran el precio promedio de los últimos días frente al de semanas atrás, para ver hacia dónde va. En {symbol} va {dir}, con {value}% de diferencia ({risk_label}): un movimiento moderado que ya se nota.",
        ],
        "medio": [
            "Las medias móviles de {symbol} apenas se separan: {value}% ({risk_label}). El precio no toma una dirección clara.",
            "Si comparas el precio promedio reciente de {symbol} con el de semanas atrás, casi no hay diferencia: {value}% ({risk_label}). El precio va sin rumbo claro.",
            "Las medias móviles muestran el precio promedio de los últimos días frente al de semanas atrás. En {symbol} casi no hay diferencia: {value}% ({risk_label}), así que el precio no muestra una dirección definida.",
        ],
        "alto": [
            "Las medias móviles de {symbol} muestran un movimiento fuerte {dir}: {value}% de diferencia ({risk_label}). El precio viene con mucho impulso.",
            "Si comparas el precio promedio reciente de {symbol} con el de semanas atrás, la diferencia es grande: {value}% ({risk_label}). El precio va claramente {dir}.",
            "Las medias móviles muestran el precio promedio de los últimos días frente al de semanas atrás. En {symbol} la diferencia es grande: {value}% ({risk_label}), y el precio va {dir} con fuerza.",
        ],
    },
    "macd": {
        "bajo": [
            "El MACD de {symbol} marca {value} puntos ({risk_label}). Mide si el precio gana o pierde fuerza en su movimiento; ahora casi no cambia.",
            "El MACD de {symbol} marca {value} puntos ({risk_label}). Indica si el precio está tomando fuerza o perdiéndola: hoy no hace ni lo uno ni lo otro.",
            "El MACD mide si el precio está ganando o perdiendo fuerza en su movimiento. En {symbol} marca {value} puntos ({risk_label}): el precio mantiene un ritmo parecido al de los últimos días, sin cambios bruscos.",
        ],
        "medio": [
            "El MACD de {symbol} marca {value} puntos ({risk_label}). Mide si el precio gana o pierde fuerza en su movimiento; hoy empuja {dir} con fuerza media.",
            "El MACD de {symbol} marca {value} puntos ({risk_label}). Indica si el precio está tomando fuerza o perdiéndola: se nota un empuje {dir}, aunque todavía suave.",
            "El MACD mide si el precio está ganando o perdiendo fuerza en su movimiento. En {symbol} marca {value} puntos ({risk_label}): el empuje {dir} es moderado, y conviene ver si se mantiene en los próximos días.",
        ],
        "alto": [
            "El MACD de {symbol} marca {value} puntos ({risk_label}). Mide si el precio gana o pierde fuerza en su movimiento; hoy empuja {dir} con mucha fuerza.",
            "El MACD de {symbol} marca {value} puntos ({risk_label}). Indica si el precio está tomando fuerza o perdiéndola: el empuje {dir} es fuerte.",
            "El MACD mide si el precio está ganando o perdiendo fuerza en su movimiento. En {symbol} marca {value} puntos ({risk_label}): el empuje {dir} es fuerte, y suele acompañar movimientos grandes del precio.",
        ],
    },
    "bandas_bollinger": {
        "bajo": [
            "Las Bandas de Bollinger de {symbol} marcan {value} ({risk_label}). Muestran el rango donde suele moverse el precio, que hoy está {llano}.",
            "Las Bandas de Bollinger marcan el rango donde suele moverse el precio. En {symbol} el dato es {value} ({risk_label}): el precio está {llano}.",
            "Las Bandas de Bollinger marcan el rango donde suele moverse el precio, y el dato dice en qué parte de ese rango está. En {symbol} marca {value} ({risk_label}): el precio está {llano}, lejos de los bordes.",
        ],
        "medio": [
            "Las Bandas de Bollinger de {symbol} marcan {value} ({risk_label}). Muestran el rango donde suele moverse el precio, que hoy está {llano}.",
            "Las Bandas de Bollinger marcan el rango donde suele moverse el precio. En {symbol} el dato es {value} ({risk_label}): el precio está {llano}, así que conviene seguirlo de cerca.",
            "Las Bandas de Bollinger marcan el rango donde suele moverse el precio, y el dato dice en qué parte de ese rango está. En {symbol} marca {value} ({risk_label}): el precio está {llano}, y a veces eso anticipa un movimiento más marcado.",
        ],
        "alto": [
            "Las Bandas de Bollinger de {symbol} marcan {value} ({risk_label}). Muestran el rango donde suele moverse el precio, que hoy está {llano}.",
            "Las Bandas de Bollinger marcan el rango donde suele moverse el precio. En {symbol} el dato es {value} ({risk_label}): el precio está {llano}, o sea, salió de su rango habitual.",
            "Las Bandas de Bollinger marcan el rango donde suele moverse el precio, y el dato dice en qué parte de ese rango está. En {symbol} marca {value} ({risk_label}): el precio está {llano}, salió de su rango habitual y podría volver a él pronto.",
        ],
    },
}

_INTERMEDIO = {
    "rsi": {
        "bajo": [
            "RSI de {symbol}: {value} puntos ({risk_label}), {zona}. Ni las subidas ni las bajadas recientes son extremas.",
            "El RSI de {symbol} está en {value} puntos ({risk_label}), {zona}. Es un valor tranquilo: no hay exceso de compras ni de ventas.",
            "El RSI compara las subidas con las bajadas recientes, en una escala de 0 a 100. {symbol} marca {value} puntos ({risk_label}), {zona}: sin presión fuerte hacia ningún lado.",
        ],
        "medio": [
            "RSI de {symbol}: {value} puntos ({risk_label}), {zona}. Cerca del centro de la escala, sin señal clara.",
            "El RSI de {symbol} está en {value} puntos ({risk_label}), {zona}. Está a mitad de camino: conviene esperar más señales antes de sacar conclusiones.",
            "El RSI compara las subidas con las bajadas recientes, de 0 a 100. {symbol} está en {value} puntos ({risk_label}), {zona}: a mitad de camino, sin una señal contundente.",
        ],
        "alto": [
            "RSI de {symbol}: {value} puntos ({risk_label}), {zona}. Movimiento extremo; suele anticipar una pausa o un giro.",
            "Ojo con el RSI de {symbol}: llegó a {value} puntos ({risk_label}), {zona}, es decir, {llano}. A veces eso precede un cambio de dirección.",
            "El RSI mide qué tan rápido se movió el precio. {symbol} marca {value} puntos ({risk_label}), {zona}: {llano}, y tras eso el precio suele frenar o corregir.",
        ],
    },
    "medias_moviles": {
        "bajo": [
            "Medias móviles de {symbol}: tendencia {trend}, {value}% entre la media corta y la larga ({risk_label}). Dirección definida, sin exceso.",
            "En {symbol}, {zona}: tendencia {trend} con {value}% de diferencia ({risk_label}). Una dirección clara pero moderada.",
            "Las medias móviles son el precio promedio de los últimos días: la corta usa pocos días y la larga muchos. En {symbol}, {zona}: tendencia {trend}, {value}% ({risk_label}).",
        ],
        "medio": [
            "Medias móviles de {symbol}: tendencia {trend}, solo {value}% entre la media corta y la larga ({risk_label}). Sin dirección clara.",
            "En {symbol}, {zona}, pero por muy poco: {value}% ({risk_label}). La tendencia {trend} todavía es débil.",
            "Las medias móviles son el precio promedio de los últimos días: la corta usa pocos días y la larga muchos. En {symbol} están casi juntas: {value}% ({risk_label}), tendencia {trend} débil.",
        ],
        "alto": [
            "Medias móviles de {symbol}: tendencia {trend} marcada, {value}% entre la media corta y la larga ({risk_label}). Movimiento con fuerza.",
            "En {symbol}, {zona} y las dos se separaron mucho: {value}% ({risk_label}). La tendencia {trend} es clara.",
            "Las medias móviles son el precio promedio de los últimos días: la corta usa pocos días y la larga muchos. Al separarse tanto como en {symbol} ({value}%, {risk_label}), la tendencia {trend} ya está instalada.",
        ],
    },
    "macd": {
        "bajo": [
            "MACD de {symbol}: histograma en {value} ({risk_label}), {zona}. Lectura {trend} suave, sin impulso claro.",
            "El MACD de {symbol} marca {value} en su histograma ({risk_label}), {zona}. Es una señal tranquila: el precio no sube ni baja con fuerza ahora.",
            "El MACD mide si el impulso del precio gana o pierde fuerza; el histograma es la distancia entre dos de sus líneas. En {symbol} vale {value} ({risk_label}), {zona}: lectura {trend} suave.",
        ],
        "medio": [
            "MACD de {symbol}: histograma en {value} ({risk_label}), {zona}. Impulso {trend} moderado.",
            "El MACD de {symbol} da una lectura {trend}: histograma en {value} ({risk_label}), {zona}. Vale observarla, aunque todavía no es contundente.",
            "El MACD mide si el impulso del precio gana o pierde fuerza; el histograma es la distancia entre dos de sus líneas. En {symbol} vale {value} ({risk_label}), {zona}: impulso {trend} intermedio.",
        ],
        "alto": [
            "MACD de {symbol}: histograma en {value} ({risk_label}), {zona}. Impulso {trend} pronunciado.",
            "El MACD de {symbol} llegó a {value} en su histograma ({risk_label}), {zona}. El precio se mueve con bastante fuerza en esa dirección.",
            "El MACD mide si el impulso del precio gana o pierde fuerza; el histograma es la distancia entre dos de sus líneas. En {symbol} vale {value} ({risk_label}), {zona}: impulso {trend} fuerte.",
        ],
    },
    "bandas_bollinger": {
        "bajo": [
            "%B de {symbol}: {value} ({risk_label}), {zona}. El precio se mueve en su rango habitual (el %B va de 0 a 1).",
            "El %B de {symbol} es {value} ({risk_label}), {zona}. El precio se mueve dentro de su rango habitual, sin señales de alerta.",
            "El %B dice dónde está el precio dentro de su rango habitual (0 es el borde inferior, 1 el superior). En {symbol} es {value} ({risk_label}): {zona}.",
        ],
        "medio": [
            "%B de {symbol}: {value} ({risk_label}), {zona}. El precio se acerca a un borde de su rango.",
            "El %B de {symbol} es {value} ({risk_label}), {zona}. El precio se acerca a un límite de su rango, así que conviene seguirlo con atención.",
            "El %B dice dónde está el precio dentro de su rango habitual (0 es el borde inferior, 1 el superior). En {symbol} es {value} ({risk_label}): {zona}, y a veces eso anticipa un movimiento más marcado.",
        ],
        "alto": [
            "%B de {symbol}: {value} ({risk_label}), {zona}. El precio salió de su rango habitual.",
            "El %B de {symbol} es {value} ({risk_label}), {zona}: el precio salió de su rango normal. Suele ser una reacción intensa que podría revertirse.",
            "El %B dice dónde está el precio dentro de su rango habitual (0 es el borde inferior, 1 el superior). En {symbol} es {value} ({risk_label}): {zona}; el precio reaccionó con fuerza y podría corregir.",
        ],
    },
}

_AVANZADO = {
    "rsi": {
        "bajo": [
            "RSI {symbol}: {value} ({risk_label}), {zona}. Sin señal de agotamiento.",
            "Mira el RSI de {symbol}: {value} ({risk_label}), {zona}. Momentum sin sesgo; nada que forzar.",
            "RSI {value} en {symbol} ({risk_label}), {zona}. Sin extremos que lean como agotamiento; la línea de 50 sigue siendo el pivote del momentum.",
        ],
        "medio": [
            "RSI {symbol}: {value} ({risk_label}), {zona}. Lectura central, sin sesgo de momentum.",
            "Mira el RSI de {symbol}: {value} ({risk_label}), {zona}. Cerca de 50, sin ventaja clara para ningún lado.",
            "RSI {value} en {symbol} ({risk_label}), {zona}. La zona 40–60 es indecisión; una ruptura en cualquier sentido daría la primera señal.",
        ],
        "alto": [
            "RSI {symbol}: {value} ({risk_label}), {zona}. Momentum extremo; riesgo de agotamiento y reversión.",
            "Mira el RSI de {symbol}: {value} ({risk_label}), {zona}. Lectura de agotamiento; espera confirmación en el precio antes de asumir giro.",
            "RSI {value} en {symbol} ({risk_label}), {zona}. El momentum llegó a un extremo: en tendencias fuertes puede sostenerse, así que conviene esperar confirmación del precio.",
        ],
    },
    "medias_moviles": {
        "bajo": [
            "MM {symbol}: {zona}, {value}% ({risk_label}). Tendencia {trend} moderada.",
            "En {symbol} {zona}: {value}% ({risk_label}). Tendencia {trend} sin extensión.",
            "MM {symbol}: {zona}, {value}% ({risk_label}). Tendencia {trend} establecida; el spread entre medias es el dato a vigilar: si se achica, el cruce se acerca.",
        ],
        "medio": [
            "MM {symbol}: {zona}, spread de {value}% ({risk_label}). Medias casi cruzadas, sin tendencia definida.",
            "En {symbol} {zona}, pero con un spread de solo {value}% ({risk_label}). Tendencia {trend} débil, riesgo de cruce falso.",
            "MM {symbol}: spread de {value}% ({risk_label}), {zona}. Con medias tan juntas el cruce es ruido; conviene esperar que el spread se amplíe.",
        ],
        "alto": [
            "MM {symbol}: {zona}, spread de {value}% ({risk_label}). Tendencia {trend} extendida.",
            "En {symbol} {zona} con un spread de {value}% ({risk_label}). Tendencia {trend} muy extendida; ojo a un retorno hacia la media.",
            "MM {symbol}: spread de {value}% ({risk_label}), {zona}. Tendencia {trend} extendida: el precio está lejos de su media y es más probable una consolidación o un retroceso.",
        ],
    },
    "macd": {
        "bajo": [
            "MACD {symbol}: histograma {value} ({risk_label}), {zona}. Momentum débil, sin impulso.",
            "Mira el MACD de {symbol}: histograma {value} ({risk_label}), {zona}. Lectura {trend} sin convicción.",
            "MACD {symbol}: histograma {value} ({risk_label}), {zona}. Impulso casi nulo; un histograma que se expande sería la primera confirmación.",
        ],
        "medio": [
            "MACD {symbol}: histograma {value} ({risk_label}), {zona}. Momentum {trend} moderado.",
            "Mira el MACD de {symbol}: histograma {value} ({risk_label}), {zona}. Momentum {trend} en desarrollo.",
            "MACD {symbol}: histograma {value} ({risk_label}), {zona}. Momentum {trend} moderado; si el histograma sigue expandiéndose, la señal gana validez.",
        ],
        "alto": [
            "MACD {symbol}: histograma {value} ({risk_label}), {zona}. Momentum {trend} fuerte.",
            "Mira el MACD de {symbol}: histograma {value} ({risk_label}), {zona}. Momentum {trend} pronunciado; vigila si el histograma empieza a contraerse.",
            "MACD {symbol}: histograma {value} ({risk_label}), {zona}. Momentum {trend} fuerte: una contracción del histograma anticiparía pérdida de impulso antes del cruce.",
        ],
    },
    "bandas_bollinger": {
        "bajo": [
            "%B {symbol}: {value} ({risk_label}), {zona}. Sin señal de ruptura.",
            "Mira el %B de {symbol}: {value} ({risk_label}), {zona}. Rango estable, sin sesgo.",
            "%B {symbol}: {value} ({risk_label}), {zona}. Sin ruptura; una contracción del ancho de bandas sería el aviso de una próxima expansión de volatilidad.",
        ],
        "medio": [
            "%B {symbol}: {value} ({risk_label}), {zona}. Presión sobre el extremo de la banda.",
            "Mira el %B de {symbol}: {value} ({risk_label}), {zona}. Aproximación al extremo; falta confirmar ruptura o rechazo.",
            "%B {symbol}: {value} ({risk_label}), {zona}. Un cierre fuera de la banda confirmaría ruptura; un rechazo apuntaría a retorno a la media.",
        ],
        "alto": [
            "%B {symbol}: {value} ({risk_label}), {zona}. Ruptura de banda; extensión respecto a la media.",
            "Mira el %B de {symbol}: {value} ({risk_label}), {zona}. Extremo estadístico: vigila retorno a la media o continuación con bandas expandiéndose.",
            "%B {symbol}: {value} ({risk_label}), {zona}. En tendencias fuertes el precio puede caminar por la banda; sin esa expansión, lo habitual es el retorno a la media.",
        ],
    },
}

TEMPLATES = {"basico": _BASICO, "intermedio": _INTERMEDIO, "avanzado": _AVANZADO}
