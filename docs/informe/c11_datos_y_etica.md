# Requerimientos de datos y consideraciones éticas (C11)

> **Borrador.** Reescríbelo con tus palabras y declara el uso de la herramienta antes de llevarlo al informe. Lo marcado **(verificar)** o **pendiente** no está confirmado. Este apartado no es asesoría legal.

## 1. Datos que usa el sistema

| Dato | Fuente | Origen | Persistencia |
|---|---|---|---|
| Precios históricos diarios de las 30 acciones del IPSA | Yahoo Finance (`yfinance`); Alpha Vantage como respaldo | Servicio público de terceros | **No se guardan.** Viven en una caché en memoria (5 min) |
| UF, dólar, TPM e IPC | mindicador.cl | API pública sobre datos del Banco Central de Chile | No se guardan (caché de 5 min) |
| Titulares de noticias | Google News RSS | Canal RSS no oficial | No se guardan (caché de 20 min) |
| Catálogo de instrumentos y glosario | `data/instruments.json`, `data/glossary.json` | Elaboración propia | Archivos del repositorio |
| Cuentas de usuario | Formulario de registro o Google | El propio usuario | Base de datos PostgreSQL |
| Registro de consultas y visitas | Generado al usar el sistema | El sistema | Base de datos PostgreSQL |

Los precios son de acceso público y se consumen en tiempo diferido, no en tiempo real (RNF-08.1).

## 2. Preprocesamiento

Antes de calcular un indicador, el extractor aplica estos pasos (`src/extractor/`):

1. **Validación de la solicitud:** el ticker debe tener entre 1 y 20 caracteres, el rango debe ser uno de 30, 90, 180 o 365 filas y el indicador debe ser uno de los cuatro definidos. Si no, la solicitud se rechaza.
2. **Limpieza de la serie:** se descartan las filas sin precio de cierre (`dropna`), se ordena por fecha y se convierte a series de tiempo.
3. **Ajuste de ventanas:** si la serie es corta, la ventana de las medias móviles se reduce a la mitad de los datos disponibles; el MACD y las bandas de Bollinger exigen un mínimo de filas y, si no se cumple, el cálculo falla con un mensaje controlado.
4. **Defensa ante valores inválidos:** si el valor resultante es nulo o no numérico (NaN), el sistema responde con un error comprensible y no guarda nada en la base.
5. **Reintentos y respaldo:** ante una falla de conexión se reintenta hasta tres veces y luego se consulta la fuente de respaldo.

La clasificación de riesgo (bajo, medio o alto) se obtiene con reglas fijas por indicador; por ejemplo, el RSI se considera alto por encima de 70 o por debajo de 30.

## 3. Datos personales

La base guarda los siguientes datos asociados a personas:

| Tabla | Datos personales | Observación |
|---|---|---|
| `users` | Nombre de usuario, correo electrónico, identificador de Google (si aplica), nivel de experiencia declarado | La contraseña se guarda como hash bcrypt, nunca en claro |
| `query_logs` | Identificador de usuario o de sesión anónima, instrumento, indicador, valor, riesgo y texto de la explicación | Permite reconstruir qué consultó cada cuenta |
| `instrument_visits` | Identificador de usuario e instrumento | Alimenta el perfil |
| `revoked_tokens` | Identificador del token | No contiene datos personales |

No se almacenan datos de pago, datos bancarios ni el portafolio del usuario. El sistema no ejecuta transacciones.

### Qué sale hacia terceros

Al proveedor del modelo de lenguaje (Groq) solo viajan el nombre de la empresa, el indicador, su valor, el nivel de riesgo y el nivel de explicación (`_build_llm_prompt` en `src/nlp/llm_explainer.py`). **No se envían correo, nombre de usuario, identificador de cuenta ni de sesión.** Las fuentes de precios reciben el ticker consultado desde el servidor, no desde el navegador del usuario.

## 4. Privacidad y marco normativo

El tratamiento de datos personales en Chile se rige por la Ley 19.628 y, según su calendario de entrada en vigencia, por la Ley 21.719 **(verificar vigencia, artículos y plazos de ambas)**. Las medidas que el sistema ya aplica:

- Minimización: solo se piden nombre de usuario, correo y contraseña.
- Almacenamiento seguro de contraseñas con bcrypt, sesión mediante token en cookie httpOnly con vencimiento de 24 horas y protección CSRF.
- Bloqueo temporal de la cuenta tras cinco intentos fallidos.
- Conexión a la base con TLS en despliegue **(verificar al contratar el servicio)**.

Brechas reconocidas:

- **No hay política de privacidad ni aviso de consentimiento** visible en la interfaz.
- **No existe una función para eliminar la cuenta ni sus registros.**
- **No hay purga** de tokens revocados ni de registros de consultas antiguos.
- Los registros de consultas guardan el texto de la explicación, lo que aumenta el volumen de datos sin que el sistema lo necesite para operar.

## 5. Consideraciones éticas

- **No es asesoría de inversión.** El sistema explica qué significa un indicador; no recomienda comprar ni vender. El pie de página lo declara ("No constituye asesoría de inversión") y el rol del modelo le prohíbe aconsejar. Un usuario principiante puede igualmente leer una explicación como una recomendación.
- **Transparencia sobre el uso de IA.** La interfaz **no indica que el texto fue generado por un modelo de lenguaje**. Es una brecha ética identificada.
- **Veracidad.** Un texto que contradice el dato sería engañoso. Por eso se valida contra el valor y la categoría del indicador antes de mostrarlo, y se avisa cuando la validación no pasa. El validador no cubre afirmaciones fuera de esas reglas.
- **Datos con retraso.** Los precios pueden no estar actualizados; el pie de página lo declara ("Datos con posibles retrasos").
- **Fuentes no oficiales.** `yfinance` y el RSS de Google News no son APIs oficiales y pueden cambiar sin aviso.
- **Inclusión.** El sistema adapta la explicación al nivel de experiencia para no excluir a quien no tiene formación financiera; el criterio que baja el nivel (dos regeneraciones) es una heurística sin validación con usuarios.

## 6. Qué no se pudo evaluar

- No hay datos de comprensión ni de uso con personas: el módulo de encuestas se retiró del alcance (ADR 0007). La efectividad sobre los usuarios no se midió.
- No se auditó el modelo preentrenado ni el LLM en busca de sesgos.
- No se evaluó la accesibilidad (contraste, lectores de pantalla) **(pendiente)**.

## Criterios y métricas del MVP

Los criterios y las métricas de evaluación del MVP se definen en el apartado C12.
