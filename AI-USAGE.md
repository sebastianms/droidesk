# AI-USAGE · DroiDesk

Cómo se usó IA para construir DroiDesk: herramientas, cómo se estructuraron el contexto y las reglas, qué se delegó, dónde intervino el humano y qué salidas se rechazaron. Cada interacción está registrada en [DEV-LOG.md](DEV-LOG.md); las decisiones de producto y arquitectura, en [DECISIONS.md](DECISIONS.md) y [`.design-logs/`](.design-logs/).

## 1. Herramientas

| Herramienta | Rol | Uso en el proyecto |
|---|---|---|
| **Claude Code · Opus 5.5, esfuerzo max** | Sesión principal: planificación | Constitución, specs, clarify, plan, tasks, ADLs, orquestación, revisión y documentación |
| **Claude Code · Sonnet 5.5, esfuerzo xHigh** | Subagentes de coding | Cada bloque de implementación se delega con un prompt autocontenido: tareas, rutas, contratos y reglas |
| [**spec-driven-dev**](.claude/skills/spec-driven-dev/SKILL.md) | Metodología | Constitution → Specify → Clarify → Plan → Tasks → Implement → Replanning, con artefactos en `specs/` |
| [**design-logger**](.claude/skills/design-logger/SKILL.md) | Memoria técnica | Un ADL por decisión de arquitectura, librería, datos o seguridad en `.design-logs/` |
| [**deckard**](.claude/skills/deckard/SKILL.md) ([agente](.claude/agents/deckard.md)) | Revisión Clean Code | Checkpoint de cada bloque; un hallazgo de criticidad ≥ 8 bloquea el commit |
| **clean-code**: [`python-clean-code`](.claude/skills/python-clean-code/SKILL.md), `clean-*`, [`boy-scout`](.claude/skills/boy-scout/SKILL.md) | Estándar de código | Reglas que aplican los subagentes al escribir y deckard al revisar |
| [**context7**](.claude/skills/context7/SKILL.md) | Documentación vigente | `npx ctx7@latest` antes de usar la API de cada librería, para no depender de lo que el modelo recuerda |
| **graft** | Navegación de código | Grafo de símbolos y llamadas, vía MCP o CLI (`graft ask`, `graft skeleton`), que reemplaza grep y lecturas de archivos completos; `graft stats` mide los tokens ahorrados |
| **rtk** | Ahorro de tokens en shell | Hook global `PreToolUse:Bash` que reescribe los comandos (`git status` → `rtk git status`) y comprime su salida |
| [**prompt-cache-control**](.claude/skills/prompt-cache-control/README.md) | Costo y latencia | Mod de claude-code-templates que muestra el hit rate del prompt cache, una cuenta regresiva hasta su vencimiento y avisa cuándo conviene `/compact` |

## 2. Cómo se estructuraron el contexto y las reglas

```mermaid
flowchart LR
  REQ["REQUIREMENTS.md<br/>prompt_inicial.txt"] --> CLAUDE["CLAUDE.md<br/>reglas y overrides"]
  CLAUDE --> SKILLS[".claude/skills<br/>SDD · design-logger · deckard · clean-code · context7"]
  SKILLS --> SPECS["specs/<br/>constitución y features"]
  SKILLS --> ADL[".design-logs/<br/>ADLs"]
  HOOK[".claude/hooks/devlog.py"] --> DEVLOG["DEV-LOG.md"]
  SPECS --> DOCS["DECISIONS.md · AI-USAGE.md"]
  ADL --> DOCS
  DEVLOG --> DOCS
```

- **[`CLAUDE.md`](CLAUDE.md)** fija el idioma, el flujo por bloque, git, el reparto de modelos y las herramientas. Cuando contradice a una skill, manda `CLAUDE.md`: aprobación por bloque en vez de por sub-tarea, y una rama por fase en vez de push directo a `main`.
- **Skills versionadas en el repo** (`.claude/skills/`): quien clone el repo trabaja con las mismas reglas. La copia de deckard se adaptó para leer los ADL de `.design-logs/` y las skills clean-code del repo. Su agente delega en la skill para no duplicar las reglas.
- **Hooks**: el del repo escribe [DEV-LOG.md](DEV-LOG.md). Los globales del usuario ejecutan deckard al terminar cada turno con cambios de código, rtk en cada comando de shell y graft.
- **Memoria**: las correcciones del usuario sobre la forma de trabajar se guardan como memoria de feedback del agente.
- **Seguridad operativa**: durante la investigación del plan, un subagente borró la caché global de build de Docker de la máquina. Desde entonces, `CLAUDE.md` prohíbe los comandos que afectan recursos globales (`docker * prune`), y todo prompt de subagente que use Docker incluye esa regla.
- **Reparto de modelos**: la sesión principal nunca cambia de modelo, porque cambiarlo invalida el prompt cache. El coding va en subagentes Sonnet, cada uno con su propio contexto. El esfuerzo max se fija por sesión con `/model`: después de reiniciar hay que volver a fijarlo.

## 3. Qué se delegó por completo al agente

| Fase | Tarea | Modelo |
|---|---|---|
| 1 · Bootstrap IA | Hook de DEV-LOG: script, tests y registro en `.claude/settings.json`, a partir de una especificación cerrada | Sonnet 5.5 xHigh |
| 1 · Bootstrap IA | Revisión Clean Code del hook y corrección de sus 2 hallazgos de criticidad 8 | Sonnet 5.5 xHigh (deckard) |
| 1 · Bootstrap IA | Copia y adaptación de skills, instalación de prompt-cache-control, `CLAUDE.md` y `.gitignore` | Opus 5.5 Max |
| 1 · Constitución | `specs/mission.md`, `tech-stack.md`, `roadmap.md` y ADL-001 a ADL-007, a partir de las 5 respuestas del usuario | Opus 5.5 Max |
| 2 · Especificación | `spec.md` y su checklist, con Clarify en 5 preguntas, y ADL-008 | Opus 5.5 Max |
| 2 · Plan | Investigación del stack con 2 subagentes en paralelo (backend y frontend), que usaron context7 y prototipos descartables | Opus 5.5 Max (subagentes) |
| 2 · Plan | `plan.md`, `research.md`, `data-model.md`, el contrato REST, `quickstart.md`, ADL-009 y las extensiones de ADL-002 a ADL-004 | Opus 5.5 Max |
| 2 · Tasks | `tasks.md`: 63 tareas en bloques (Setup, Foundational, US1 a US5 y Polish), con trazabilidad de cada FR a sus tareas | Opus 5.5 Max |
| 3 · Setup | Las dos apps (FastAPI y React con Vite), Dockerfiles, nginx, `docker-compose.yml`, CI por app y el contrato inicial, con 2 subagentes en paralelo y uno de integración | Sonnet 5.5 xHigh |
| 3 · Foundational | API: configuración, base de datos, modelos, migración 0001, el dominio en TDD (ciclo de vida, calendario hábil y SLA), JWT, autorización, historial, catálogos y datos de demo. Web: design system del droide, cliente tipado, ingreso simulado, guardas por rol y vistas vacías | Sonnet 5.5 xHigh |
| 3 · Checkpoints | Revisión de deckard por bloque y corrección de sus hallazgos, incluidos 2 de criticidad 8 (el dominio acoplado a SQLModel y FastAPI) | Sonnet 5.5 xHigh (deckard) |
| 3 · Orquestación | Revisión del código entregado, prueba de punta a punta del stack Docker, extensiones de ADL-002, ADL-004, ADL-005 y ADL-006, y actualización de los artefactos de SDD | Opus 5.5 Max |
| 4 · US1 | API: esquemas, `TicketService` con transiciones condicionales, endpoints y tests. Web: formulario de nuevo ticket, "Mis tickets", detalle con acciones y confirmación, y componentes de formulario. Un subagente por app, en secuencia, unidos por el contrato regenerado | Sonnet 5.5 xHigh |
| 4 · Checkpoint | Revisión de deckard sobre la API y luego sobre el diff completo, sin hallazgos de criticidad ≥ 8; se aplicaron 4 refactors menores en la API | Sonnet 5.5 xHigh (deckard) |
| 4 · Orquestación | Prueba en navegador de los escenarios 1, 2, 4 y 12 contra un stack Docker aislado, corrección del escenario 14 del quickstart, y extensiones de ADL-002, ADL-004 y ADL-008 | Opus 5.5 Max |
| 5 · US2 | API: vistas de la cola, `take` con carrera probada con hilos, efectos de cada transición y el colaborador `TicketSla`. Web: cola con pestañas, listado compartido y acciones por rol | Sonnet 5.5 xHigh |
| 5 · Checkpoint | Revisión de deckard sobre la API y sobre el diff completo, sin hallazgos de criticidad ≥ 8; se aplicaron sus ajustes menores en la API | Sonnet 5.5 xHigh (deckard) |
| 5 · Orquestación | Prueba en navegador de los escenarios 6, 7, 10, 11 y 14 con varios agentes a la vez, contra un stack aislado, y extensiones de ADL-004 y ADL-008 | Opus 5.5 Max |
| 6 · US3 | Historial en el detalle (API, contrato y línea de tiempo en la web), con un solo subagente para todo el bloque | Sonnet 5.5 xHigh |
| 6 · Checkpoint | deckard detectó una función con 4 argumentos (criticidad 8): se corrigió y se activó la regla `PLR0913` de ruff para que no se repita | Sonnet 5.5 xHigh (deckard) |
| 6 · Orquestación | Prueba en navegador del escenario 15 contra un stack aislado y extensión de ADL-002 | Opus 5.5 Max |

## 4. Dónde intervino el humano y por qué

| Momento | Intervención | Efecto |
|---|---|---|
| Preguntas iniciales | Rechazó el cuestionario para aclarar dudas antes de responder | Se reformularon las preguntas con más contexto ([DEV-LOG #1](DEV-LOG.md)) |
| Alcance opcional | Propuso SLA + Adjuntos y pidió una segunda opinión | Tras la recomendación eligió SLA + Comentarios ([DEV-LOG #2](DEV-LOG.md), [criterio](DECISIONS.md#alcance-opcional)) |
| Constitución | Cambió la meta de cobertura propuesta (90 % en la API y 70 % en la web) por Pareto 80/20: 80 % total y 90 % en el flujo crítico | Nuevo [ADL-007](.design-logs/ADL-007-pareto-coverage-gates.md) y gates en `CLAUDE.md` y `tech-stack.md` |
| Clarify de la feature 001 | Respondió las 5 preguntas: prioridad sugerida por el solicitante y ajustable por el agente, pausa del SLA en espera, reactivación al comentar, cancelación solo desde Abierto y plazos por prioridad | Spec sin ambigüedades y [ADL-008](.design-logs/ADL-008-ticket-lifecycle-six-states.md) con el ciclo de vida |
| Revisión del SLA | Cambió de opinión sobre los plazos aceptados (4, 8, 24 y 72 h corridas): tiempo hábil de lunes a viernes, de 09:00 a 18:00, para un equipo chico. Lo urgente sigue corto (Crítica 4 h y Alta 1 día hábil) y Media y Baja se alargan a 3 y 5 días hábiles | Se reabrió la respuesta 5 de Clarify; spec, constitución y deuda técnica (feriados) actualizadas |
| Fase 3 · Foundational | Recordó mantener actualizados los archivos de SDD durante la implementación | `tasks.md` marca `[/]` y `[x]` por bloque, y el roadmap y los pendientes de research se actualizan en cada checkpoint; quedó como regla en la memoria del agente |
| Fase 3 · Foundational | Detuvo al subagente de la API antes de que entregara su reporte | El orquestador verificó el estado en que quedó el código, completó el checkpoint y delegó las correcciones en un subagente nuevo |
| Fase 3 · Revisión de la app | Revisó el ambiente Docker y pidió un login real: la autenticación simulada debe responder OK con cualquier usuario y contraseña. Eligió el selector de perfil entre 3 opciones | FR-001 revisado, [ADL-005](.design-logs/ADL-005-simulated-auth-signed-token.md) enmendado, contrato sin `GET /auth/users` y login reimplementado en la API y la web |
| Fase 3 · Revisión del login | Pidió no crear usuarios sin límite: usuarios precreados por perfil y un ícono "?" en el login que los liste, para la demo. Luego pidió que el "?" explique que son usuarios de demo | Login solo para usuarios existentes, sin selector de perfil, con `GET /auth/users` público y reducido para alimentar la ayuda ([ADL-005](.design-logs/ADL-005-simulated-auth-signed-token.md)) |

## 5. Qué salidas del agente se rechazaron

| Salida | Motivo |
|---|---|
| Primer cuestionario de 4 preguntas | El usuario necesitaba aclarar las opcionales antes de responder |
| Ingreso eligiendo un usuario de una lista, sin contraseña (Fase 3) | El usuario esperaba un login: "la autenticación simulada se refiere a que el proceso de autenticación debe retornar siempre OK, da igual el usuario y password" |
| Login que crea usuarios nuevos con un selector de perfil (Fase 3) | El usuario no quería crear usuarios sin límite: "deberíamos tener usuarios ya creados por rol" |

## 6. graft, rtk, prompt-cache-control y context7 en la práctica

- **graft**: indexa el repo y responde "dónde está X / quién llama a Y" con el código inline, sin leer archivos enteros. En el bootstrap no había código de la app que indexar y sus herramientas MCP no quedaron expuestas en la sesión, así que se usa por CLI y por sus hooks globales; entra de lleno desde la Fase 2.
- **rtk**: activo desde el primer comando del proyecto vía hook global; el ahorro acumulado se mide con `rtk gain`.
- **prompt-cache-control**: instalado en la Fase 1 con `npx claude-code-templates@latest --mod observability/prompt-cache-control`. Las métricas de cache de cada turno (leída, escrita, hit rate) quedan también en DEV-LOG.
- **context7**: obligatorio antes de escribir código contra FastAPI, SQLModel, Alembic, React o Vite; las consultas quedan registradas en DEV-LOG como comandos `ctx7`. En la constitución se usó, junto con los registros de npm y PyPI, para confirmar las versiones vigentes antes de fijar el stack (Vite 8, TypeScript 7, SQLAlchemy 2.1). En el plan, los subagentes de investigación lo combinaron con prototipos descartables y encontraron incompatibilidades que la memoria del modelo no traía:
  - TypeScript 7 todavía rompe la generación de tipos, así que se fija TypeScript 6;
  - React Router 8 eliminó `react-router-dom`;
  - el `TestClient` de FastAPI ahora usa `httpx2`;
  - SQLModel exige fechas con zona horaria ([research.md](specs/001-ticketing-mvp/research.md)).
