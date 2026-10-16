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
