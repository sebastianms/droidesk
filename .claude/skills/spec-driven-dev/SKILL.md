---
name: spec-driven-dev
description: Use when building any new feature, project, or significant code change. Implements the Spec-Driven Development (SDD) methodology — specifications drive implementation, not the other way around. Guides the full lifecycle from constitution → specify → clarify → plan → tasks → implement.
---

# 🌱 Spec-Driven Development (SDD)

> "Specifications don't serve code — code serves specifications."
> — GitHub Spec Kit

## The Core Idea

Spec-Driven Development **inverts the traditional power structure**: instead of writing code and hoping it matches requirements, you write precise, complete specifications that **generate** implementation. The spec is the source of truth. Code is its expression.

## When to Use This Skill

- Starting a **new project** (greenfield)
- Adding a **significant feature** to an existing project (brownfield)
- **Refactoring or modernizing** an existing system
- Any work that involves **multiple files, components, or phases**
- When the user invokes any SDD-related command

**Do NOT use for:** trivial one-line fixes, typo corrections, simple config changes, or exploratory questions.

---

## The SDD Lifecycle

The methodology follows a strict sequential flow. Each phase produces artifacts that feed the next.

```
Constitution → Specify → Clarify → Plan → Tasks → Implement ─┐
                  ↑                                           │
                  │                                           ▼
                  └─────────────── Replanning ◄───────────────┘
                                   (before next Specify)
```

Replanning is a **cross-feature validation phase** that runs between completing one feature and starting the next one. It prevents drift by forcing a reconciliation pass over existing specs, tasks, code, and roadmap.

---

## Phase 0: Constitution

**Purpose**: Establish the project's foundation ("Carta Fundamental") before writing any code. These documents constrain ALL subsequent decisions.

### What It Produces

1. `specs/mission.md` — High-level mission, vision, justification, core workflows, and success metrics.
2. `specs/roadmap.md` — An implementation plan broken down into very small, independently testable phases ("shippable slices").
3. `specs/tech-stack.md` — System design, technology choices, API/database schemas, and component architecture.

### How to Execute

1. **Check if constitution files exist** (`mission.md`, `roadmap.md`, `tech-stack.md` in `specs/`).
2. **If they do NOT exist**, act as an architect (inspired by the `/carrera` workflow) and create them by interviewing the user about:
   - **Business & Workflow (`mission.md`)**: What is the core loop? What are the success metrics?
   - **Architecture (`tech-stack.md`)**: Are there strict stack preferences (e.g., Next.js, Python, SQLite)? Key external dependencies?
   - **Scope (`roadmap.md`)**: What constitutes the MVP (minimum viable first phases)? What is out of scope?
3. **If they exist**, load them and apply any user-requested amendments.
4. All documents MUST be highly detailed, resembling production-grade documentation (e.g., using Mermaid diagrams for workflows, tables for APIs and schemas).
5. Ensure consistency: the roadmap MUST align with the architecture in the tech-stack, and both MUST serve the goals in the mission.

### File Structures

**`specs/mission.md`**
- Overview & Motivation
- Core Clinical Workflow (or equivalent business logic)
- Scope (MVP vs. Deferred)
- Success Metrics

**`specs/tech-stack.md`**
- System Design & Component Architecture
- Technology Stack & Configuration
- Data Layer (Schema) & API Reference
- Processing Pipelines / Workflows

**`specs/roadmap.md`**
- Phase 1: Setup & Constitution
- Phase 2: Foundational Elements
- Phase 3+: User Stories (shippable slices)

---

## Phase 1: Specify

**Purpose**: Transform a natural-language feature description into a complete, structured specification focused on WHAT and WHY — never HOW.

### What It Produces

- `specs/<NNN-feature-name>/spec.md` — The feature specification.
- `specs/<NNN-feature-name>/checklists/requirements.md` — Quality checklist.

### How to Execute

1. **Parse the user's feature description** and extract: actors, actions, data, constraints.
2. **Generate a short name** (2-4 words, action-noun format): e.g., "user-auth", "analytics-dashboard".
3. **Create the feature directory**: `specs/<NNN-short-name>/` where NNN is the next sequential number.
4. **Write `spec.md`** using the template structure below.
5. **Critical Rules**:
   - Focus on **WHAT** users need and **WHY** — never mention tech stack, APIs, or code structure.
   - Written for **business stakeholders**, not developers.
   - Make **informed guesses** based on context and industry standards.
   - Maximum **3 `[NEEDS CLARIFICATION]` markers** — only for decisions that significantly impact scope, security, or UX.
   - Every requirement MUST be **testable and unambiguous**.
   - Document reasonable defaults in the Assumptions section.
6. **Run quality validation** against a checklist. Fix issues up to 3 iterations.
7. If `[NEEDS CLARIFICATION]` markers remain, present options in a table format (max 3 questions).

### Spec Template Structure

```markdown
# Feature Specification: [FEATURE NAME]

**Feature Branch**: `[NNN-feature-name]`
**Created**: [DATE]
**Status**: Draft

## User Scenarios & Testing *(mandatory)*

### User Story 1 - [Brief Title] (Priority: P1)
[Plain-language user journey]

**Why this priority**: [Value justification]
**Independent Test**: [How to test this story alone]
**Acceptance Scenarios**:
1. **Given** [state], **When** [action], **Then** [outcome]

---

### User Story 2 - [Brief Title] (Priority: P2)
[... same structure]

### Edge Cases
- What happens when [boundary condition]?
- How does system handle [error scenario]?

## Requirements *(mandatory)*

### Functional Requirements
- **FR-001**: System MUST [specific, testable capability]
- **FR-002**: System MUST [specific, testable capability]

### Key Entities *(if data involved)*
- **[Entity]**: [What it represents, key attributes]

## Success Criteria *(mandatory)*

### Measurable Outcomes
- **SC-001**: [User-focused, technology-agnostic, measurable metric]
- **SC-002**: [User-focused, technology-agnostic, measurable metric]

## Assumptions
- [Reasonable default documented]
```

### Success Criteria Rules

Success criteria MUST be:
- **Measurable**: Include specific metrics (time, percentage, count)
- **Technology-agnostic**: No frameworks, languages, or databases
- **User-focused**: Outcomes from user/business perspective
- **Verifiable**: Testable without knowing implementation details

**Good**: "Users can complete checkout in under 3 minutes"
**Bad**: "API response time is under 200ms" (too technical)

---

## Phase 2: Clarify

**Purpose**: Systematically detect and reduce ambiguity in the spec through structured questioning BEFORE planning.

### How to Execute

1. **Load the spec** and perform a structured ambiguity scan across these categories:
   - Functional Scope & Behavior
   - Domain & Data Model
   - Interaction & UX Flow
   - Non-Functional Quality Attributes (performance, security, reliability)
   - Integration & External Dependencies
   - Edge Cases & Failure Handling
   - Constraints & Tradeoffs
   - Terminology & Consistency

2. **Generate up to 5 targeted questions** (maximum), prioritized by:
   - Impact × Uncertainty heuristic
   - Category coverage balance
   - Only questions whose answers materially impact architecture, data modeling, or test design

3. **Ask ONE question at a time** (sequential, not batched):
   - For multiple-choice: Present a **recommended option** with reasoning, then a table of all options.
   - For short-answer: Provide a **suggested answer** with reasoning.
   - User can accept with "yes" or provide their own answer.

4. **After each accepted answer**, immediately:
   - Append to a `## Clarifications` section with `### Session YYYY-MM-DD`
   - Update the relevant spec section (requirements, user stories, edge cases, etc.)
   - Save the spec file atomically after each integration.

5. **Stop conditions**: All ambiguities resolved, user says "done", or 5 questions reached.

6. **Report**: Number of questions asked, sections touched, coverage summary, suggested next command.

---

## Phase 3: Plan

**Purpose**: Transform business requirements into a technical implementation plan with architecture, tech stack, and design documents.

### What It Produces

- `specs/<feature>/plan.md` — Technical implementation plan
- `specs/<feature>/research.md` — Technology research and decisions
- `specs/<feature>/data-model.md` — Entity definitions and relationships
- `specs/<feature>/contracts/` — API specs, interface contracts
- `specs/<feature>/quickstart.md` — Key validation scenarios

### How to Execute

1. **Load the spec**, `mission.md`, `tech-stack.md`, and `roadmap.md`.
2. **Constitution Check**: Verify the plan aligns with the architecture in `tech-stack.md` and the goals in `mission.md`. ERROR on unjustified violations.
3. **Phase 0 — Research**: For each unknown or NEEDS CLARIFICATION in technical context:
   - Create research tasks
   - Consolidate findings in `research.md` with: Decision, Rationale, Alternatives Considered
4. **Phase 1 — Design**:
   - Extract entities from spec → `data-model.md` (fields, relationships, validation rules)
   - Define interface contracts → `contracts/` (appropriate for project type: APIs, CLIs, etc.)
   - Generate validation scenarios → `quickstart.md`
5. **Fill `plan.md`** using the template below.

### Plan Template Structure

```markdown
# Implementation Plan: [FEATURE]

**Branch**: `[NNN-feature-name]` | **Date**: [DATE]

## Summary
[Primary requirement + technical approach]

## Technical Context
**Language/Version**: [e.g., Python 3.11]
**Primary Dependencies**: [e.g., FastAPI, SQLAlchemy]
**Storage**: [e.g., PostgreSQL]
**Testing**: [e.g., pytest]
**Target Platform**: [e.g., Linux server]
**Project Type**: [e.g., web-service]

## Constitution Check
[Gate validations against tech-stack and mission]

## Project Structure
[Concrete directory layout for this feature]

## Complexity Tracking
> Fill ONLY if Constitution Check has violations
| Violation | Why Needed | Simpler Alternative Rejected Because |
```

### Key Rules

- Mark unknowns as `NEEDS CLARIFICATION` — resolve in research.md
- ERROR on unjustified gate failures
- Keep plan.md **high-level and readable** — detailed specs go in supporting files
- Every technology choice MUST trace back to a specific requirement

---

## Phase 4: Tasks

**Purpose**: Break the plan into an actionable, dependency-ordered task list organized by user story.

### What It Produces

- `specs/<feature>/tasks.md` — Executable task breakdown

### How to Execute

1. **Load**: plan.md (required), spec.md (required for user stories), data-model.md, contracts/, research.md
2. **Generate tasks organized by user story** (not by technology layer):
   - **Setup Sub-tasks** — Project initialization
   - **Foundational Sub-tasks** — Blocking prerequisites (MUST complete before ANY user story)
   - **User Story Sub-tasks** — Grouped per user story, in priority order (P1, P2, P3...)
   - **Polish Sub-tasks** — Cross-cutting concerns
3. **Within each user story's sub-tasks**: Models → Services → Endpoints → Integration
4. **Tests are OPTIONAL** — only if explicitly requested in the spec.

### Task Format (REQUIRED)

Every task MUST use this exact format:

```text
- [ ] [TaskID] [P?] [Story?] Description with exact file path
```

- **`- [ ]`**: Markdown checkbox (ALWAYS required)
- **TaskID**: Sequential `T001`, `T002`, etc.
- **`[P]`**: Only if parallelizable (different files, no dependencies)
- **`[Story]`**: `[US1]`, `[US2]` etc. — REQUIRED in user story sub-tasks, omitted in Setup/Foundational/Polish
- **Description**: Clear action with exact file path

**Correct**: `- [ ] T012 [P] [US1] Create User model in src/models/user.py`
**Wrong**: `- [ ] Create User model` (missing ID, story label, file path)

### Dependencies & Execution Order

- Setup → Foundational → User Stories (can be parallel) → Polish
- Each user story MUST be independently testable
- Models before services, services before endpoints
- Mark completed tasks as `[x]`

---

## Phase 5: Implement

**Purpose**: Execute all tasks from tasks.md, building the feature according to the plan.

### How to Execute

1. **Validate prerequisites**: mission.md, tech-stack.md, roadmap.md, spec.md, plan.md, tasks.md all exist.
2. **Check checklists** (if `checklists/` exists): Report status. If incomplete, ask user before proceeding.
3. **Load context**: tasks.md, plan.md, data-model.md, contracts/, research.md, quickstart.md
4. **Project setup**: Create appropriate ignore files (.gitignore, etc.) based on tech stack.
5. **Execute tasks group by group**:
   - Complete each group of sub-tasks before moving to the next
   - Respect `[P]` parallel markers and sequential dependencies
   - Follow TDD if tests were requested (tests FAIL first, then implement)
6. **Progress tracking & Validation**:
   - **Mark In-Progress**: Before starting any sub-task, update `tasks.md` and mark the task as `[/]`.
   - **MANDATORY Validation**: After each individual sub-task (T001, T002, etc.), report progress and EXPLICITLY ask for user validation.
   - **STOP & WAIT**: Never advance to the next sub-task until the user has explicitly validated the previous one.
   - **Immediate Update**: Update `tasks.md` marking the task as `[x]` immediately AFTER user approval.
   - Halt on any task failure or if the user rejects the result.
   - Provide clear error messages with debugging context.
7. **Block Checkpoint** — ejecutar al terminar cada bloque de tasks (Setup, Foundational, cada User Story, Polish). Ejecutar en este orden y NO avanzar si alguno falla:
   1. **Lint sin warnings**: ejecutar las herramientas de calidad de cada stack tocado en el bloque. Detectar fallos de lint ANTES de Deckard y commits — son los más baratos de corregir y los que tumban CI primero. Ejemplos: `ruff check app/ tests/` (Python), `pnpm lint` + `pnpm typecheck` (TS/JS), `golangci-lint run` (Go), `cargo clippy -- -D warnings` (Rust). Si el proyecto define herramientas adicionales en CI o en un `CLAUDE.md` del repo, también deben pasar. Cero warnings, no solo cero errores.
   2. **Tests verdes con cobertura**: ejecutar la suite completa del stack (`pytest --cov` / `npm test -- --coverage` / Playwright según aplique). Reportar resultado y cobertura. No avanzar si hay regresiones ni si la cobertura cae por debajo del umbral del proyecto (default 90% si no está documentado).
   3. **Deckard review**: invocar el skill `deckard` sobre los cambios del bloque. Corregir toda violación de criticidad ≥ 8 antes de continuar.
   4. **ADL check**: evaluar si alguna decisión técnica del bloque es nueva o contradice un ADL existente. Si es así, crear o actualizar el ADL correspondiente en `.design-logs/`. Si la decisión ya estaba cubierta por un ADL existente, documentar solo una nota de extensión en ese ADL.
   5. **Commits pequeños**: agrupar los archivos del bloque por responsabilidad (modelos, repositorios, servicios, frontend, tests) y crear un commit por grupo. Mensajes en formato `feat|fix|refactor(NNN-feature/bloque): descripción corta`.
   6. **Push**: hacer `git push origin main` tras los commits del bloque.

   > **Regla de oro**: lint y tests primero, commit después. Nunca diferir lint a "lo arreglo después" — si el bloque deja warnings, el bloque no está cerrado. CI los va a detectar y bloquear igualmente, mejor evitar el ida-y-vuelta de fixes triviales.
8. **Completion & Next Steps**:
   - Verify all tasks done, features match spec, and tests pass.
   - **Check Roadmap**: Consult `specs/roadmap.md` to identify the next Phase or User Story.
   - **Proactive Loop**: Before proposing the next **Phase 1: Specify**, run **Phase 5.5: Replanning** to validate project-wide consistency. Only after Replanning produces a clean report (or its corrections are applied) should the next Specify begin.

---

## Phase 5.5: Replanning — Cross-Feature Validation

**Purpose**: Verify that the project as a whole is internally consistent before starting a new feature. Specs, tasks, code, and roadmap drift apart silently as work progresses; Replanning forces a reconciliation pass so the next spec starts from solid ground.

**When**: After completing a feature's Implement phase, **before** starting the next Specify. Also valid as a standalone "health check" whenever the user suspects drift.

### What It Produces

A structured audit report with:
- **Estado general** — one paragraph verdict.
- **Constitution check** — mission/roadmap/tech-stack present and current.
- **Per-feature status** — tasks completed vs. pending, files referenced vs. existing on disk.
- **Inconsistencies found** — tasks marked `[x]` but files missing, tests named differently than documented, roadmap phases not reflecting real progress, unused code, orphan tests.
- **Deferred items** — explicitly `[-]` tasks with their ADL/rationale links.
- **ADL coverage** — decisions implemented but not documented.
- **Recommended corrections** — ordered by blocking-ness.

### How to Execute

1. **Load constitution**: Read `specs/mission.md`, `specs/roadmap.md`, `specs/tech-stack.md`. Verify they exist and match the current implementation.

2. **Walk every feature directory** (`specs/NNN-*/`):
   - Read `tasks.md` and count `[x]` / `[ ]` / `[-]` / `[/]`.
   - For each `[x]` task that references a file path: verify the file exists at that path. If the file is elsewhere (renamed/consolidated), flag as a **naming inconsistency** (not a missing file).
   - Verify that deferred `[-]` / `[ ]` tasks with deferral notes reference a concrete destination phase/feature in `roadmap.md`. A deferral without a roadmap anchor is flagged as **orphan deferral** — a CRITICAL inconsistency.

3. **Cross-check roadmap vs. reality**:
   - For each phase in `roadmap.md`, check whether its bullets match the completion state of the corresponding feature.
   - Flag phases marked `[ ]` whose feature is actually `[x]` complete (stale roadmap).
   - Flag phases marked `[DONE]` whose feature still has open tasks (premature close).

4. **Code presence audit**:
   - For a sample of critical files mentioned across tasks, verify they exist.
   - Run the test suite briefly to confirm no import errors from renamed modules.

5. **ADL coverage check**:
   - Identify significant decisions implemented (new architecture, new library, security boundary) that lack an ADL in `.design-logs/`.

6. **Produce the report** and present it to the user. The report is **read-only by default** — corrections happen only with user approval, in a second pass.

7. **Corrections pass** (if the user approves):
   - Update `roadmap.md` to reflect real completion state.
   - Update stale `tasks.md` headers (Status line).
   - Rename documented paths in `tasks.md` to match actual file locations (or rename the file, whichever the user prefers).
   - Redact any ADLs flagged as missing.
   - Commit each correction group separately (`chore(roadmap): ...`, `chore(NNN-feature): fix task file path`, `docs(adl-NNN): ...`).

### Rules

- **Read-only first**: Produce the audit report before changing anything. Do not "fix" silently while auditing.
- **Don't invent problems**: If all specs, tasks, and files are consistent, say so explicitly and move on. Replanning is not an excuse for busywork.
- **Respect deferred items**: `[-]` tasks with a documented rationale (ADL reference, "pending review manual", etc.) are NOT inconsistencies.
- **Naming inconsistencies ≠ missing code**: If a task says "add `test_no_connection.py`" but the test lives in `test_chat_with_data_agent.py`, verify the test exists before flagging. File location drift is a documentation fix, not a missing implementation.
- **Block if constitution drifts**: If `mission.md` / `tech-stack.md` no longer match the implementation, stop and ask the user to clarify before starting the next Specify.

### Completion Criteria

Replanning is complete when either:
- The audit report shows zero inconsistencies (ready to Specify), OR
- All flagged inconsistencies have been corrected and committed (ready to Specify), OR
- The user has explicitly chosen to defer specific corrections (document the deferral in the report).

---

## Phase 6: Analyze — Optional

**Purpose**: Cross-artifact consistency and coverage analysis. Run after Tasks, before Implement.

### What It Does (READ-ONLY — never modifies files)

1. Build internal models of requirements, user stories, task coverage, and constitution documents.
2. Run detection passes:
   - **Duplication**: Near-duplicate requirements
   - **Ambiguity**: Vague adjectives without metrics, unresolved placeholders
   - **Underspecification**: Requirements missing acceptance criteria
   - **Constitution Alignment**: Violations of architecture in tech-stack or mission goals (always CRITICAL)
   - **Coverage Gaps**: Requirements with zero tasks, tasks with no requirement
   - **Inconsistency**: Terminology drift, conflicting requirements
3. Produce a severity-tagged report (CRITICAL > HIGH > MEDIUM > LOW).
4. Recommend next actions before implementation.

---

## Directory Structure

All SDD artifacts live under `specs/` in the project root:

```text
specs/
├── mission.md                      # Project mission and scope (Phase 0)
├── tech-stack.md                   # System design and tech stack (Phase 0)
├── roadmap.md                      # High-level implementation plan (Phase 0)
├── 001-feature-name/               # Feature directory (Phase 1+)
│   ├── spec.md                     # Feature specification
│   ├── plan.md                     # Technical implementation plan
│   ├── tasks.md                    # Task breakdown
│   ├── research.md                 # Technology research & decisions
│   ├── data-model.md              # Entity definitions
│   ├── quickstart.md              # Validation scenarios
│   ├── contracts/                  # Interface contracts
│   │   ├── api-spec.json
│   │   └── ...
│   └── checklists/                # Quality checklists
│       └── requirements.md
├── 002-another-feature/
│   └── ...
```

---

## AI Behavior Rules

### Idioma de Interacción

**OBLIGATORIO**: Toda interacción con el usuario DEBE ser en **Español Neutro** — profesional, claro, sin jerga regional. Esto incluye:
- Preguntas de clarificación
- Reportes de progreso y estado
- Mensajes de error y sugerencias
- Resúmenes de cada fase

**Excepciones** (se mantienen en inglés):
- Identificadores técnicos estándar: `FR-001`, `SC-001`, `T001`, `[US1]`, `[P]`, `[NEEDS CLARIFICATION]`
- Contenido de templates y estructuras de archivos (headings de spec.md, plan.md, etc.)
- Términos técnicos sin traducción precisa: "user story", "acceptance criteria", "edge case", "tech stack"
- Código fuente y rutas de archivos

### Always

1. **Seguir el orden del lifecycle**: Constitution → Specify → Clarify → Plan → Tasks → Implement
2. **Separar el QUÉ del CÓMO**: Los specs describen necesidades del usuario; los plans describen el enfoque técnico
3. **Trazabilidad total**: Cada decisión técnica se traza a un requisito; cada tarea se traza a un user story
4. **La constitución es ley**: Las divergencias respecto al `mission.md` o `tech-stack.md` son CRITICAL y bloquean la implementación
5. **User stories independientemente testeables**: Cada story entrega valor por sí sola
6. **Marcar unknowns explícitamente**: Usar `[NEEDS CLARIFICATION]` — nunca asumir silenciosamente en decisiones críticas
7. **Specs agnósticos de tecnología**: Sin frameworks, lenguajes ni bases de datos en spec.md
8. **Iterar, no one-shot**: Usar loops de clarificación y validación para refinar calidad
9. **Continuidad Proactiva**: Al completar la implementación de una característica o fase del roadmap, consultar siempre `specs/roadmap.md` y proponer iniciar el flujo SDD (`Specify`) para el siguiente ítem de forma proactiva.
10. **Replanning antes de Specify**: Antes de arrancar una nueva feature, ejecutar **Phase 5.5: Replanning** para validar que specs, tasks, código y roadmap están alineados. Las inconsistencias se corrigen antes de empezar el siguiente spec, no después.
11. **Deferral con destino explícito**: Toda tarea que se difiere DEBE documentar tres cosas: (a) por qué se difiere, (b) la fase o feature concreta donde se retomará, (c) qué condición debe cumplirse para activarla. Un deferral sin destino es deuda técnica invisible. Formato obligatorio en tasks.md: `→ **diferido a [Fase/Feature]** ([condición])`. Actualizar `roadmap.md` para reflejar el destino.

### Nunca

1. **Nunca saltar fases**: No pasar de una idea vaga a código
2. **Nunca poner detalles de implementación en specs**: Eso pertenece a plan.md
3. **Nunca dejar texto contradictorio**: Al clarificar, reemplazar el statement ambiguo anterior
4. **Nunca exceder límites de preguntas**: Máx 3 marcadores NEEDS CLARIFICATION, máx 5 preguntas de clarificación
5. **Nunca modificar archivos durante análisis**: Analyze es estrictamente read-only
6. **Nunca crear features especulativos**: Cada feature se traza a un user story concreto
7. **Nunca tratar el primer intento como final**: Iterar sobre specs antes de implementar
8. **Nunca diferir sin anclar**: No marcar una tarea como diferida sin actualizar el roadmap con su fase destino. Un `[ ]` huérfano sin roadmap entry es peor que no tenerlo — genera falsa sensación de completitud y se pierde entre features.

### Priorizar

- **Simplicidad sobre ingeniería excesiva**: Empezar simple, agregar complejidad solo cuando esté justificada
- **Integración sobre aislamiento**: Testear en ambientes reales, no artificiales
- **Modularidad sobre monolitos**: Límites claros entre componentes
- **Observabilidad sobre opacidad**: Todo debe ser inspeccionable y debuggeable
