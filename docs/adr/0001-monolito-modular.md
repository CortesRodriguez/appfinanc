# ADR 0001: monolito modular en Flask

- Estado: aceptada
- Requerimientos relacionados: RNF-07

## Contexto y problema

El sistema tiene extracción de datos, generación de explicaciones, autenticación, perfil y presentación. Lo desarrolla una sola persona, con un alcance de prototipo académico. Hay que decidir cómo se despliega y cómo se separan las responsabilidades.

## Criterios de decisión

- Simplicidad operativa para un desarrollador y una defensa oral.
- Separación clara de responsabilidades (RNF-07.1).
- Posibilidad de extraer un módulo después si hace falta.

## Opciones consideradas

### A. Monolito modular (elegida)
- Pro: un proceso, un despliegue; los módulos se llaman como funciones Python.
- Pro: la separación en paquetes ya refleja la vista de desarrollo del modelo 4+1.
- Contra: todos los módulos escalan juntos.

### B. Microservicios
- Pro: escalado y despliegue independientes.
- Contra: complejidad operativa (red, versionado de contratos, observabilidad) desproporcionada para el alcance.

## Decisión

Un solo proceso Flask con paquetes en `src/`: `extractor`, `nlp`, `auth`, `profile` y `web`. Los módulos se comunican por funciones públicas (`get_indicator`, `generate_explanation`, `get_detail_level`).

## Consecuencias

- Positivas: despliegue y depuración simples; fácil de explicar.
- Negativas: `src/profile/routes.py` y `src/web/routes.py` repiten parte de la orquestación de una consulta (deuda documentada en `docs/diseno/04_diagrama_componentes.md`). Refactor propuesto: un `query_service.py` compartido.
- Tras el ADR 0007, el paquete `src/evaluation/` solo conservaba los modelos `QueryLog` e `InstrumentVisit`; se eliminó y los modelos pasaron a `src/profile/models.py`, sin cambios de esquema.

## Verificación

Estructura de `src/`; dependencias entre módulos con `grep "^from src"`.

## Referencias

- Fowler, M. (2015). *MonolithFirst*. martinfowler.com (verificar).
- Kruchten, P. (1995). The 4+1 view model of architecture. *IEEE Software*, 12(6), 42–50.
