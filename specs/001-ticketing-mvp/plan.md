# Implementation Plan: Ticketing MVP

**Feature**: `001-ticketing-mvp` · **Rama de planificación**: `phase/02-mvp-spec` | **Date**: 2026-10-16
**Input**: [spec.md](spec.md) · **Artefactos**: [research.md](research.md) · [data-model.md](data-model.md) · [contracts/rest-api.md](contracts/rest-api.md) · [quickstart.md](quickstart.md)

## Summary

Un sistema de tickets con dos perfiles: el solicitante crea y sigue sus tickets, y el agente toma tickets de una cola ordenada por vencimiento y los mueve por un ciclo de vida de 6 estados. Cada cambio queda en un historial inmutable. Solicitante y agente conversan con comentarios, y el SLA corre en tiempo hábil según la prioridad.

Técnicamente son dos apps independientes unidas por un contrato OpenAPI:
- **API**: FastAPI y SQLModel sobre SQLite. Las reglas viven en funciones puras de dominio: la tabla de transiciones y el calendario hábil.
- **Web**: SPA en React con tipos y hooks generados desde el contrato.

## Technical Context

**Language/Version**: Python 3.14 (API) · TypeScript 6.0 (web)
**Primary Dependencies**: FastAPI 0.143, SQLModel 0.0.48, SQLAlchemy 2.1, Alembic 1.20, PyJWT 2.15, pydantic-settings 2.16 · React 19.3, Vite 8.3, React Router 8.4, TanStack Query 5, openapi-fetch 0.17, openapi-react-query 0.5
**Storage**: SQLite en un volumen Docker; migraciones con Alembic
**Testing**: pytest 9 + pytest-cov, con reloj inyectable (API) · Vitest 5 + Testing Library + jsdom (web)
**Target Platform**: contenedores Linux con Docker Compose, en local
**Project Type**: web, con dos apps independientes (`apps/api` y `apps/web`)
**Performance Goals**: la cola y el detalle responden en menos de 200 ms con el volumen del MVP; no hay pruebas de carga en el MVP
**Constraints**:
- SQL portable;
- fechas en UTC;
- sin CORS;
- un solo comando de setup;
- cobertura ≥ 80 % total y ≥ 90 % en el flujo crítico.

**Scale/Scope**: ~800 personas, decenas de tickets por día y 7 usuarios de demo.

## Constitution Check

| Gate | Fuente | Cómo lo cumple el plan | Estado |
|---|---|---|---|
| Dos apps independientes; solo las une el contrato | [ADL-001](../../.design-logs/ADL-001-two-apps-openapi-contract.md) | Proyectos, Dockerfile y CI separados; `contracts/openapi.json` generado y verificado en CI | ✅ |
| Routers delgados y dominio puro | [ADL-002](../../.design-logs/ADL-002-fastapi-sqlmodel-backend.md) | `lifecycle.py` y `calendar.py` sin imports de framework; los servicios orquestan | ✅ |
| SQLite con SQL portable y fechas UTC | [ADL-003](../../.design-logs/ADL-003-sqlite-mvp-postgres-path.md) | Enums como texto, `UTCDateTime` y migraciones con Alembic | ✅ |
| La web no duplica reglas de negocio | [ADL-004](../../.design-logs/ADL-004-react-vite-spa.md) | Las acciones visibles salen de `allowed_actions` | ✅ |
| Rol leído de la base de datos | [ADL-005](../../.design-logs/ADL-005-simulated-auth-signed-token.md) | `identity/authorization.py` carga el usuario por `sub` | ✅ |
| Mismo origen y un solo comando de setup | [ADL-006](../../.design-logs/ADL-006-docker-compose-same-origin.md) | nginx con proxy de `/api` y `setup.sh` en la fase 9 | ✅ |
| Cobertura de 80 % total y 90 % en el flujo crítico | [ADL-007](../../.design-logs/ADL-007-pareto-coverage-gates.md) | Dos reportes por app, ambos en CI | ✅ |
| Ciclo de vida de 6 estados | [ADL-008](../../.design-logs/ADL-008-ticket-lifecycle-six-states.md) | Tabla declarativa única | ✅ |
| SLA en tiempo hábil | [ADL-009](../../.design-logs/ADL-009-sla-business-time.md) | `BusinessCalendar` con dos funciones puras | ✅ |
| Alcance: obligatorios + SLA + comentarios | [mission.md](../mission.md) | Sin funcionalidades fuera del alcance | ✅ |

Resultado: sin violaciones.

## Project Structure

### Documentación de la feature

```
specs/001-ticketing-mvp/
├── spec.md · plan.md · research.md · data-model.md · quickstart.md · tasks.md
├── contracts/rest-api.md
└── checklists/requirements.md
```

### Código

```
contracts/openapi.json                 # generado por la API, consumido por la web
apps/api/
├── pyproject.toml · uv.lock · Dockerfile · .dockerignore · docker-entrypoint.sh
├── migrations/                        # Alembic (env.py, script.py.mako, versions/)
├── scripts/export_openapi.py
├── src/droidesk_api/
│   ├── main.py                        # crea la app: routers, handler de errores, lifespan
│   ├── models.py                      # importa todos los modelos (para Alembic)
│   ├── seed.py                        # datos de demo
│   ├── core/                          # config.py, db.py, errors.py, clock.py, security.py (JWT)
│   ├── identity/                      # models.py, router.py (users, login, me), authorization.py
│   ├── tickets/                       # models.py (Ticket, Category, Comment), lifecycle.py (dominio),
│   │                                  # service.py, schemas.py, router.py
│   ├── audit/                         # models.py (TicketEvent), recorder.py
│   └── sla/                           # models.py (SlaPolicy), calendar.py y status.py (dominio), router.py
└── tests/
    ├── unit/                          # lifecycle, calendar, estado del SLA
    └── api/                           # endpoints por user story
apps/web/
├── package.json · vite.config.ts · tsconfig*.json · biome.json · Dockerfile · nginx.conf
└── src/
    ├── app/                           # router.tsx, guards.ts, providers.tsx, AppLayout.tsx
    ├── api/                           # schema.d.ts (generado), client.ts
    ├── features/
    │   ├── auth/                      # LoginPage, session.ts
    │   ├── requester/                 # MyTicketsPage, NewTicketForm
    │   ├── agent/                     # QueuePage
    │   └── tickets/                   # TicketDetailPage, TicketActions, Timeline, CommentBox, luces
    ├── ui/                            # tokens.css, Button, Panel, Light, EmptyState, DroidLogo
    └── test/setup.ts
docker-compose.yml · setup.sh · .github/workflows/{api,web}.yml
```

## Implementation Strategy

El esquema completo y el núcleo del dominio (la tabla de transiciones y el calendario hábil) se construyen en **Foundational**, porque toda user story los necesita: así los datos son consistentes desde el primer ticket. Cada user story agrega servicios, endpoints e interfaz sobre esa base.

| Fase del roadmap | Bloques de `tasks.md` | Entregable verificable | Quickstart |
|---|---|---|---|
| 3 · Foundation | Setup + Foundational | Ingreso simulado y vistas vacías por rol, con CI verde en ambas apps | 3 |
| 4 · US1 | Crear, listar y cancelar mis tickets | El solicitante crea un ticket y lo sigue | 1, 2, 4, 12 |
| 5 · US2 | Cola, tomar y transiciones | El agente toma, deja en espera, resuelve; el solicitante cierra o reabre | 6, 7, 10, 11, 14 |
| 6 · US3 | Historial en el detalle | La línea de tiempo completa e inmutable | 15 |
| 7 · US4 | Comentarios | Conversación, y la vuelta automática desde En espera | 8, 9 |
| 8 · US5 | SLA visible | Selector y ajuste de prioridad, luces de estado y cola ordenada por vencimiento | 5, 13 y los bordes del SLA |

Las migraciones avanzan con las fases: la inicial (Foundational) crea usuarios, categorías, políticas, tickets e historial, y la de US4 agrega los comentarios.

## Complexity Tracking

Sin violaciones de la constitución. La complejidad aceptada está justificada en su propio ADL:
- el calendario hábil, porque el SLA en horas corridas castigaría a un equipo chico ([ADL-009](../../.design-logs/ADL-009-sla-business-time.md));
- los dos reportes de cobertura, uno total y otro del flujo crítico ([ADL-007](../../.design-logs/ADL-007-pareto-coverage-gates.md)).
