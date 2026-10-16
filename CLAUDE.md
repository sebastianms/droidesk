# DroiDesk · Reglas del proyecto para agentes de IA

DroiDesk es el MVP de un sistema de tickets de soporte para una organización de ~800 personas. Enunciado: [`REQUIREMENTS.md`](REQUIREMENTS.md) · Prompt de arranque: [`prompt_inicial.txt`](prompt_inicial.txt).

Este archivo manda sobre las skills genéricas cuando se contradicen. Los overrides están marcados con **(override)**.

## Idioma
- Conversación, specs, ADLs y documentación: **español neutro**.
- Código, identificadores, archivos y ramas: **inglés**.
- Commits: Conventional Commits con la descripción en español neutro, p. ej. `feat(001-mvp/us1): permite crear tickets`.

## Metodología
- **Spec-Driven Development** ([`.claude/skills/spec-driven-dev`](.claude/skills/spec-driven-dev/SKILL.md)): Constitution → Specify → Clarify → Plan → Tasks → Implement → Replanning. Artefactos en `specs/`.
- **Design logs** ([`.claude/skills/design-logger`](.claude/skills/design-logger/SKILL.md)): cada decisión de arquitectura, librería, esquema de datos o seguridad crea o extiende un ADL en `.design-logs/`.
- **Deckard** ([skill](.claude/skills/deckard/SKILL.md) y [agente](.claude/agents/deckard.md)): revisión Clean Code al cierre de cada bloque. Se corrige todo hallazgo de criticidad ≥ 8.
- **Clean Code + SOLID, Less is More**: `python-clean-code` y `clean-*` para Python; `boy-scout` para TypeScript/React.

## Flujo por bloque
1. **(override)** Se ejecutan **todas** las tareas de un bloque (Setup, Foundational, cada User Story, Polish) sin pedir validación por sub-tarea.
2. Checkpoint del bloque: lint sin warnings → tests verdes con cobertura → deckard → ADL check.
3. Resumen al usuario y **esperar su aprobación explícita** antes de hacer commit y push.
4. Commits pequeños por responsabilidad y push a la rama de la fase.

## Git (trunk-based)
- `main` es el tronco. **(override)** Una rama por fase del roadmap (`phase/NN-slug`, p. ej. `phase/01-setup-constitution`) y un PR por fase hacia `main`. Después del commit inicial no se hace push directo a `main`.
- `gh` tiene activa otra cuenta por defecto: los PR se crean con `GH_TOKEN=$(gh auth token --user sebastianms) gh pr create ...`, sin cambiar la cuenta activa.

## Modelos
- **Planificación** (constitution, specify, clarify, plan, tasks, replanning, ADLs, documentación): sesión principal con **Opus 5.5, esfuerzo max**.
- **Coding** (implement, scripts, Docker, tests): **subagentes Sonnet 5.5 con esfuerzo xHigh** (`model: sonnet`, `effort: xhigh`). Cada subagente recibe un prompt autocontenido con tareas, rutas, contratos y las reglas de este archivo.

## Herramientas
- **context7** ([skill](.claude/skills/context7/SKILL.md), `npx ctx7@latest`): consultar la documentación vigente antes de usar la API de una librería (FastAPI, SQLModel, Alembic, React, Vite, etc.).
- **graft**: navegar el código antes de usar grep o leer archivos completos, vía MCP (`graft_find_code`, `graft_trace_calls`, `graft_file_api`) o CLI (`graft ask`, `graft skeleton`, `graft callers`). Reindexar con `graft build` tras cambios grandes.
- **rtk**: proxy de shell que comprime la salida de los comandos; actúa solo, vía hook global.
- **prompt-cache-control** ([mod](.claude/skills/prompt-cache-control/README.md)): vigilar el prompt cache. No cambiar de modelo en la sesión principal y usar `/compact` antes de retomar un contexto grande con el cache expirado.

## Arquitectura
- `apps/api` (FastAPI + SQLModel + SQLite) y `apps/web` (React + Vite + TypeScript) son apps independientes, cada una con dependencias, Dockerfile y tests propios. **Nunca** se importan entre sí: solo se comunican por el contrato OpenAPI.
- El detalle vive en `specs/tech-stack.md`. SQLite en el MVP; PostgreSQL en el plan de escalamiento.

## Documentación viva
- `DEV-LOG.md` lo escribe el hook [`.claude/hooks/devlog.py`](.claude/hooks/devlog.py). Se edita a mano solo para backfill o correcciones. Un prompt que contenga `#nolog` o "no documentes este prompt" no se registra.
- `DECISIONS.md` y `AI-USAGE.md` se actualizan al cerrar cada fase con un resumen breve y enlaces a `specs/`, `.design-logs/` y `DEV-LOG.md`.
- En `AI-USAGE.md`, las intervenciones y las salidas rechazadas registran solo lo que decide el usuario, no las revisiones entre agentes.
