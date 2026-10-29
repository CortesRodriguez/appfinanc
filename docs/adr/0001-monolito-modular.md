# 0001. Monolito modular en Flask

## Status

Aceptada (registrada a posteriori).

## Context

El sistema tiene extracción de datos, generación de explicaciones, autenticación, perfil y presentación. Lo desarrolla una sola persona, con un alcance de prototipo académico. Hay que decidir cómo se despliega y cómo se separan las responsabilidades.

Requerimientos relacionados: RNF-07 (organización modular del código).

Alternativas consideradas:

- **Monolito modular.** Un proceso, un despliegue; los módulos se llaman como funciones Python y la separación en paquetes ya refleja la vista de desarrollo del modelo 4+1. Costo: todos los módulos escalan juntos.
- **Microservicios.** Permiten escalar y desplegar cada parte por separado, pero suman complejidad operativa (red, versionado de contratos, observabilidad) desproporcionada para el alcance.

Se priorizó la simplicidad operativa para un desarrollador y para la defensa oral, la separación clara de responsabilidades (RNF-07.1) y la posibilidad de extraer un módulo más adelante.

Referencias (verificar antes de citar):

- Fowler, M. (2015). *MonolithFirst*. martinfowler.com.
- Kruchten, P. (1995). The 4+1 view model of architecture. *IEEE Software*, 12(6), 42–50.

## Decision

Un solo proceso Flask con paquetes en `src/`: `extractor`, `nlp`, `auth`, `profile`, `services` y `web`. Los módulos se comunican por funciones públicas (`get_indicator`, `generate_explanation`, `get_detail_level`).

## Consequences

Se vuelve más fácil:

- Desplegar y depurar: un solo proceso.
- Explicar la arquitectura en la defensa.
- Compartir la orquestación de una consulta (indicador → explicación → registro), que vive en `src/services/query_service.py` y usan `src/web/routes.py` y `src/profile/routes.py`. Antes estaba copiada en tres endpoints.

Se vuelve más difícil:

- Escalar un módulo por separado.
- Mantener las rutas delgadas: siguen accediendo a `db` directamente (deuda del ORM difuso, documentada en `docs/diseno/04_diagrama_componentes.md`).

Tras el ADR 0007, el paquete `src/evaluation/` solo conservaba los modelos `QueryLog` e `InstrumentVisit`; se eliminó y los modelos pasaron a `src/profile/models.py`, sin cambios de esquema.

Verificación: estructura de `src/` y dependencias entre módulos con `git grep "^from src"`.
