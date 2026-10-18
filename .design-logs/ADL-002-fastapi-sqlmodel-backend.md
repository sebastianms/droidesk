# ADL-002: API en Python con FastAPI y SQLModel

**Fecha:** 2026-10-16
**Estado:** Activo
**Área:** Backend
**Autor:** Usuario + AI Session

---

## Contexto

El usuario eligió Python para la API. El código debe ser simple de leer, con Clean Code y SOLID, y deckard lo revisa con las skills `python-clean-code` y `clean-*`. La API debe exponer un contrato OpenAPI para la web ([ADL-001](ADL-001-two-apps-openapi-contract.md)) y persistir en SQLite con un camino a PostgreSQL.

---

## Decisión

Python 3.14 con FastAPI, SQLModel como ORM y modelos, Alembic para migraciones y uv para dependencias. Calidad con ruff, mypy y pytest. Endpoints y sesiones de base de datos síncronos, en capas router → servicio → dominio, con el dominio en funciones puras.

---

## Justificación

FastAPI entrega validación por tipos, inyección de dependencias (útil para autorizar por rol) y el OpenAPI automático que hace de contrato. SQLModel usa una sola clase para la tabla y la validación, sobre SQLAlchemy, lo que reduce código de mapeo y mantiene la portabilidad entre motores. Lo síncrono basta para el volumen del MVP con SQLite y evita la complejidad de los drivers asíncronos.

---

## Consecuencias

### ✅ Positivas
- OpenAPI y documentación interactiva (`/docs`) sin código extra.
- Dominio testeable sin servidor ni base de datos.
- Mismo modelo de datos sobre SQLite hoy y PostgreSQL mañana.

### ⚠️ Trade-offs aceptados
- SQLModel sigue en versiones `0.0.x`: su API puede cambiar, así que se fija la versión en `uv.lock`.
- Los endpoints síncronos corren en el threadpool; a escala alta se reevalúa async junto con PostgreSQL.

---

## Alternativas Consideradas

| Alternativa | Razón de descarte |
|-------------|-------------------|
| Rails 8 API | El usuario eligió Python; más convención implícita que leer |
| Node (Fastify) + Drizzle | Las skills clean-code del proyecto son de Python |
| Django REST Framework | Más peso del necesario para una API pequeña; el OpenAPI no es nativo |
| SQLAlchemy sin SQLModel | Duplica modelos de tabla y esquemas de validación |

---

## Decisiones Relacionadas
- [ADL-001](ADL-001-two-apps-openapi-contract.md): el OpenAPI de FastAPI es el contrato.
- [ADL-003](ADL-003-sqlite-mvp-postgres-path.md): motor de base de datos.
- [ADL-005](ADL-005-simulated-auth-signed-token.md): autorización con dependencias de FastAPI.

---

## Notas para el AI (Memoria Técnica)
- El dominio (transiciones, SLA) no importa FastAPI ni SQLModel: recibe y devuelve datos simples.
- Routers delgados: validan, autorizan y delegan en un servicio. Sin lógica de negocio en los routers.
- Usa dependencias con `Annotated` para la sesión y el usuario actual.
- Consulta context7 antes de usar APIs de FastAPI, SQLModel o Alembic: las versiones cambian rápido.
- No cambies a async ni agregues un repository pattern genérico sin un ADL que lo justifique.

---

## Extensión 2026-10-16 · Plan de la feature 001

Verificado en [research.md](../specs/001-ticketing-mvp/research.md); la decisión de fondo no cambia.
- **Versiones**: fastapi 0.143.3 (sin `[standard]`), sqlmodel 0.0.48 (tope `<0.0.49`), sqlalchemy 2.1.5 (respaldo 2.0.55), pydantic 2.14.1, alembic 1.20.0, uvicorn 0.54.0 y pyjwt 2.15.1, todo sobre `python:3.14.8-slim-trixie` y uv 0.13.1.
- **Librerías nuevas**:
  - `pydantic-settings` para la configuración con prefijo `DROIDESK_`;
  - `tzdata` para tener las mismas reglas de zona horaria en todos los entornos;
  - `httpx2` como cliente del `TestClient` en desarrollo, porque Starlette 1.8 lo prefiere.
- **Errores**: una jerarquía `DomainError` con un solo handler que responde `{code, message}`. Las rutas declaran sus respuestas 4xx para que el OpenAPI las tipifique. El 422 de validación conserva el formato estándar de FastAPI.
- **Enums**: `StrEnum` con valores en minúscula, guardados como texto (`native_enum=False`).
- **Contrato**: `scripts/export_openapi.py` lo regenera; importar la app no debe exigir secretos ni tocar la base.

---

## Extensión 2026-10-17 · Fundaciones (Fase 3)

La decisión de fondo no cambia. Se fijaron estos detalles al implementarla:
- **Dominio sin framework, verificado con un test**:
  - los enums viven en módulos `enums.py` con solo stdlib (`identity`, `tickets`, `sla` y `audit`), y los modelos los importan desde ahí;
  - `core/errors.py` contiene solo la jerarquía `DomainError`, y la parte HTTP (`ErrorBody`, `error_responses` y el handler) vive en `core/http_errors.py`;
  - un test importa `lifecycle`, `status` y `calendar` en un subproceso y falla si se carga FastAPI, Starlette, SQLModel, SQLAlchemy o pydantic.

  Deckard lo detectó como criticidad 8: la primera versión importaba los enums desde los modelos SQLModel. Esto corrige la indicación de T013 de poner los enums en `models.py`.
- **App sin efectos al crearse**:
  - `create_app()` no lee secretos ni abre la base: la configuración se resuelve como dependencia cacheada (`get_settings`) y el engine se crea en el lifespan;
  - las migraciones usan `DatabaseSettings`, que no exige el secreto.
- **Contrato legible**: el `operationId` es el nombre de la ruta (`login`, `read_me`, `list_categories`, etc.). La documentación se sirve en `/api/docs` y `/api/openapi.json`, para que nginx la exponga en el mismo origen.
- **Entrada acotada y sin eco**:
  - el login valida el patrón y el largo del `username` y el largo del `password` ([ADL-005](ADL-005-simulated-auth-signed-token.md));
  - un handler global de `RequestValidationError` conserva el formato estándar del 422, pero le quita la clave `input`. `SecretStr` no basta, porque FastAPI devuelve el valor crudo en `input`, y con un campo faltante devuelve el body completo;
  - la configuración oculta el valor de entrada en sus errores, para que un secreto inválido no termine en los logs.
