# Roadmap: DroiDesk

Cada fase es una rama `phase/NN-slug` y un PR hacia `main` (trunk-based). Dentro de una fase, cada bloque cierra con su checkpoint (lint → tests → deckard → ADL) y con la aprobación del usuario antes del commit y el push. La planificación corre en Opus 5.5 Max y el coding en subagentes Sonnet 5.5 xHigh ([CLAUDE.md](../CLAUDE.md)).

Las fases 4 a 8 son las user stories de la feature `001-ticketing-mvp`; sus IDs definitivos quedan en `specs/001-ticketing-mvp/spec.md`.

## Phase 1: Setup & Constitution — `phase/01-setup-constitution` [EN CURSO]

- [x] Bootstrap IA: skills en el repo, hook de DEV-LOG, prompt-cache-control y `CLAUDE.md`.
- [x] Constitución: `mission.md`, `tech-stack.md` y `roadmap.md`.
- [x] ADLs fundacionales: ADL-001 a ADL-007.

## Phase 2: MVP Specification & Plan — `phase/02-mvp-spec`

- [ ] Specify: `specs/001-ticketing-mvp/spec.md` y su checklist de calidad.
- [ ] Clarify (máximo 5 preguntas): quién define la prioridad, efecto de "En espera" sobre el SLA, reglas de cierre y reapertura.
- [ ] Plan: `plan.md`, `research.md` (versiones verificadas con context7), `data-model.md`, `contracts/` y `quickstart.md`.
- [ ] Tasks: `tasks.md`, organizado por user story.

## Phase 3: Foundational Elements — `phase/03-foundation`

- [ ] Esqueletos de `apps/api` y `apps/web`, cada uno con lint, tests y Dockerfile.
- [ ] Base de datos, migraciones y datos de demo: usuarios, categorías y políticas de SLA.
- [ ] Ingreso simulado con token y autorización por rol.
- [ ] Contrato OpenAPI con tipos generados en la web y CI por app.
- [ ] Layout por rol y tema visual del droide.

## Phase 4: Crear y seguir tickets (solicitante) — `phase/04-requester-tickets`

- [ ] El solicitante crea un ticket y ve el estado de los suyos.

## Phase 5: Cola del agente — `phase/05-agent-queue`

- [ ] El agente ve la cola, toma un ticket y cambia su estado según la máquina de estados.

## Phase 6: Historial del ticket — `phase/06-ticket-history`

- [ ] Solicitante y agente ven qué pasó con un ticket, quién lo hizo y cuándo.

## Phase 7: Comentarios — `phase/07-comments`

- [ ] Solicitante y agente conversan dentro del ticket; cada comentario queda en el historial.

## Phase 8: SLA por prioridad — `phase/08-sla`

- [ ] Prioridad con plazo comprometido, vencimiento visible, luces de estado del SLA y cola ordenada por urgencia.

## Phase 9: Packaging & Initial Setup — `phase/09-packaging`

- [ ] `setup.sh`: un comando que verifica Docker, pide la configuración, genera el secreto, levanta todo y muestra las URLs y los usuarios de demo.
- [ ] `README.md` con diagramas Mermaid del flujo y de la arquitectura.
- [ ] Smoke test end-to-end del recorrido principal.
- [ ] Versión final de `DECISIONS.md`, `AI-USAGE.md` y de la estrategia de calidad.

## Phase 10: Scalability — `phase/10-scalability`

- [ ] `SCALABILITY.md`: tres estrategias para 50.000 tickets al mes y 5 áreas de soporte, con pros, contras, riesgos y mitigaciones. Todas contemplan PostgreSQL.
- [ ] Fase de decisión con el usuario. La estrategia elegida alimenta la sección "qué romperías o rediseñarías" de `DECISIONS.md`.
- [ ] Destino de lo diferido en la misión: autenticación real, varias áreas, horario hábil en el SLA y cierre automático.
