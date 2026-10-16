# DEV-LOG · DroiDesk

Bitácora de cada interacción humano ↔ IA del proyecto. La escribe el hook [`.claude/hooks/devlog.py`](.claude/hooks/devlog.py), registrado en [`.claude/settings.json`](.claude/settings.json). Las entradas anteriores a su activación son un *backfill* manual y están marcadas como tal.

Lectura resumida en [AI-USAGE.md](AI-USAGE.md) · decisiones en [DECISIONS.md](DECISIONS.md) · ADLs en [`.design-logs/`](.design-logs/).

---

## 🛰️ Sesión `2680e3d9` · startup · `claude-opus-5-5` · *backfill*

### #1 · 🧑 Usuario
> `/model` → Opus 5.5 con esfuerzo max para esta sesión.
>
> Prompt de arranque (texto completo en [`prompt_inicial.txt`](prompt_inicial.txt)): construir la aplicación de [`REQUIREMENTS.md`](REQUIREMENTS.md) (originalmente `requirements.txt`) con spec-driven-development, design-logs y revisión de deckard; MVP con 3 estrategias de escalabilidad; DECISIONS.md, AI-USAGE.md y DEV-LOG.md (este último vía hook del repo); skills adjuntas al repo; README con Mermaid y setup con Docker; look & feel de droide de Star Wars; Opus 5.5 Max para planificar y Sonnet 5.5 xHigh para codificar; aprobación por bloque antes de commit y push; una rama y un PR por fase; las 5 preguntas más importantes.

#### 🤖 Claude · `claude-opus-5-5` · esfuerzo max
- **Exploración:** repo vacío (`main` sin commits) y remoto `sebastianms/droidesk` público y vacío; la cuenta activa de `gh` solo tiene permiso READ sobre el repo. Revisa las skills spec-driven-dev, design-logger, deckard (skill y agente), la familia clean-code y context7. Detecta los hooks globales: deckard en `Stop`, rtk en `PreToolUse:Bash` y graft.
- **Búsqueda:** `prompt-cache-control` no estaba instalado; lo identifica como un mod de claude-code-templates (aitmpl).
- Presenta los supuestos por defecto (auth simulada, look astromecánico, idioma, flujo git, skills en el repo, testing por riesgo) y un cuestionario de 4 preguntas (stack, opcionales, modularidad, modelos).

**🧑 Usuario — rechaza el cuestionario para aclarar dudas.** Solo deja respondido el stack: **Python + React**.

### #2 · 🧑 Usuario
> Sobre las funcionalidades opcionales, elijo SLA y adjuntos, ya que los adjuntos aclaran el problema que ocurre o consideras que los comentarios son mas importantes?

#### 🤖 Claude · `claude-opus-5-5` · esfuerzo max
- Recomienda **SLA + Comentarios** ([criterio completo en DECISIONS.md](DECISIONS.md#alcance-opcional)):
  - **SLA por prioridad**: responde "¿cuánto demoran?" con un plazo comprometido por prioridad y ordena la cola por vencimiento.
  - **Comentarios**: sacan la conversación del correo y la dejan en la trazabilidad del ticket; además hacen viable el estado "En espera del solicitante".
  - **Adjuntos** quedan fuera: suman almacenamiento, validación y seguridad, y en el MVP se mitigan pegando un enlace a la evidencia.
- Reformula las preguntas pendientes y agrega la quinta (prompt-cache-control).

**🧑 Usuario — respuestas:**

| Tema | Decisión |
|---|---|
| Stack | Python (FastAPI + SQLModel + Alembic + pytest) + React (Vite + TypeScript + Vitest) |
| Opcionales | **SLA por prioridad + Comentarios** (cambia su elección inicial de Adjuntos) |
| Modularidad | 2 apps independientes, `apps/api` y `apps/web`, unidas solo por el contrato OpenAPI |
| Modelos | Sesión principal Opus 5.5 Max (planificación); subagentes Sonnet 5.5 xHigh (coding) |
| prompt-cache-control | Instalarlo en este repo |

#### 🤖 Claude · Fase 1, bloque *Bootstrap IA*
- Verifica en la documentación oficial el esquema de entrada de los hooks (`Stop.last_assistant_message`, `SubagentStop.agent_transcript_path`, el stdout de `UserPromptSubmit` se inyecta al contexto).
- Instala `prompt-cache-control` con `npx claude-code-templates@latest --mod observability/prompt-cache-control` y revisa su código: solo lee settings, sin red.
- Delega el hook de DEV-LOG a un subagente Sonnet 5.5 xHigh con una especificación cerrada.
- Copia las skills al repo, adapta deckard para leer `.design-logs/` y escribe `CLAUDE.md` y `.gitignore`.
- El subagente entrega el hook: `devlog.py` (solo stdlib; nunca escribe en stdout y siempre sale con 0), tests con `unittest` y `.claude/settings.json` con 7 eventos. En el smoke test con el transcript real, el hit de prompt cache fue de 97 %.
- **Deckard** (Sonnet 5.5 xHigh) rechaza la primera versión con 2 hallazgos de criticidad 8: una respuesta podía falsificar los encabezados `### #N` y la redacción dejaba pasar 4 formatos de credenciales. Se corrigen y se agregan tests de regresión.
- Al revisar el log en vivo, la sesión principal detecta que los reportes de subagentes quedaban registrados como "🧑 Usuario". Se corrige el hook: 179 tests en verde y ruff sin warnings.
- graft: la CLI funciona, pero sus herramientas MCP no se exponen en la sesión y todavía no hay código de la app que indexar.
- Cierra el bloque con el checkpoint (lint, tests y deckard; sin ADL, porque son decisiones de herramientas y no de arquitectura) y pide aprobación para commit y push.
- *Desde aquí el registro lo continúa el hook.*

### #3 · 🧑 Usuario
> quita eso del AI-USAGE.md, no es necesario, hay que documentar solo las salidas que yo rechazo

#### 🤖 Claude · `claude-opus-5-5` · esfuerzo max · ⏱ 1m 9s
- **Herramientas:** Edit ×3 · Bash ×2 · Read ×1
- **Archivos modificados:** `DEV-LOG.md`, `AI-USAGE.md`, `CLAUDE.md`
- **Tokens:** entrada 8 · cache leída 1.2M · cache escrita 10.9k · salida 5.5k · hit 99%

<details><summary>Respuesta</summary>

El bloque *Bootstrap IA* está terminado y verificado. Espero tu aprobación para el commit y el push.

**Qué incluye**
- **Hook de DEV-LOG** (`.claude/hooks/devlog.py`, registrado en `.claude/settings.json`). Ya funciona: tu último mensaje quedó como #3. En cada turno registra:
  - el prompt, las herramientas usadas, los archivos tocados, los commits y PR, los subagentes, los tokens y el porcentaje de prompt cache reutilizado;
  - nunca fecha ni hora, y oculta todo lo que parezca un secreto.

  Ignora los mensajes internos de los subagentes y no registra los prompts con `#nolog` o "no documentes este prompt".
- **Skills en `.claude/skills/`:** spec-driven-dev, design-logger, deckard (ahora lee `.design-logs/`), python-clean-code, la familia `clean-*`, boy-scout y context7. El agente deckard queda en `.claude/agents/`.
- **prompt-cache-control** en `.claude/skills/prompt-cache-control/`.
- **Documentación:**
  - `CLAUDE.md` con las reglas del proyecto y en qué difiere de las skills;
  - `AI-USAGE.md` en su primera versión;
  - `DECISIONS.md` con el alcance opcional;
  - `DEV-LOG.md`.
- `.gitignore`.

**Verificaciones antes del commit**

| Paso | Resultado |
|---|---|
| Lint | ruff sin warnings |
| Tests | 179 en verde |
| Deckard | Encontró 2 problemas graves en el hook (los dos que te conté antes); quedaron corregidos y con tests |
| ADL | No aplica: son decisiones de herramientas; los ADL empiezan con la constitución |

**Commits que propongo**
1. En `main`: `chore: agrega enunciado, prompt de arranque y .gitignore`, y push.
2. En la rama `phase/01-setup-constitution`:
   - `chore(ai): agrega skills del proyecto y agente deckard`
   - `chore(ai): instala el mod prompt-cache-control`
   - `feat(ai): registra cada interacción en DEV-LOG con un hook del repo`
   - `docs: agrega CLAUDE.md, AI-USAGE, DECISIONS y DEV-LOG`

   Push de la rama. El PR lo abro al cerrar la fase, después de la constitución.

**Después del push** tienes que reiniciar Claude Code para que cargue prompt-cache-control: `/exit`, luego `claude --continue`, y aceptar el aviso de confianza del workspace. Al volver reviso si las herramientas MCP de graft aparecen y sigo con el bloque de constitución: `mission.md`, `tech-stack.md`, `roadmap.md` y los primeros ADL.

**Tengo dos preguntas:**
1. ¿Apruebas los commits y el push?
2. ¿Renombro `requirements.txt` a `REQUIREMENTS.md` antes del commit inicial? En la raíz de un repo Python, GitHub, Dependabot y `pip install -r` lo leen como una lista de dependencias. Si prefieres conservar el nombre original del enunciado, lo dejo tal cual.

</details>

### #4 · 🧑 Usuario
> 1. Si
> 2. si, de acuerdo, puede confundir

#### 🤖 Claude · `claude-opus-5-5` · esfuerzo max · ⏱ 1m 51s
- **Herramientas:** Bash ×5 · Edit ×3 · Write ×1 · Read ×1
- **Archivos modificados:** `REQUIREMENTS.md`, `CLAUDE.md`, `AI-USAGE.md`, `DEV-LOG.md`
- **Git:** `e849226` chore: agrega enunciado, prompt de arranque y .gitignore · `6d8e011` docs: agrega CLAUDE.md, AI-USAGE, DECISIONS y DEV-LOG
- **Tokens:** entrada 12 · cache leída 1.9M · cache escrita 11.2k · salida 9.4k · hit 99%

<details><summary>Respuesta</summary>

Los commits y el push están hechos, y el remoto coincide con lo local.

**En `main`:**
- `e849226` chore: agrega enunciado, prompt de arranque y .gitignore. Ya incluye `REQUIREMENTS.md`, con las mismas 291 palabras del original y formato Markdown.

**En `phase/01-setup-constitution`:**
- `3a29ca8` chore(ai): agrega skills del proyecto y agente deckard
- `7015e4c` chore(ai): instala el mod prompt-cache-control
- `06f9c2e` feat(ai): registra cada interacción en DEV-LOG con un hook del repo
- `6d8e011` docs: agrega CLAUDE.md, AI-USAGE, DECISIONS y DEV-LOG

Actualicé las referencias al nuevo nombre en `CLAUDE.md`, `AI-USAGE.md` y la entrada #1 de DEV-LOG. `prompt_inicial.txt` sigue diciendo `requirements.txt`, porque es tu prompt original tal como lo escribiste. El PR de la fase lo abro cuando cerremos el bloque de constitución.

**Ahora te toca reiniciar** para que cargue prompt-cache-control:
1. `/exit`
2. En `~/Apps/droidesk`, ejecuta `claude --continue`.
3. Si aparece el aviso de confianza del workspace, acéptalo. Vas a ver el medidor del caché sobre el prompt, y `/cache` abre su panel.

Cuando vuelvas, escríbeme "continúa". Verifico que el mod y las herramientas MCP de graft estén cargados y arranco el bloque de constitución: `specs/mission.md`, `specs/tech-stack.md`, `specs/roadmap.md` y los primeros ADL (monorepo con 2 apps, stack, SQLite y auth simulada).

</details>

*Sesión finalizada (prompt_input_exit)*

## 🛰️ Sesión `2680e3d9` · resume

- **Cache:** probablemente vigente · inactivo 15s · contexto 319.3k tokens · re-escritura estimada US$2.55

### #5 · 🧑 Usuario
> Continua

#### 🤖 Claude · `claude-opus-5-5` · esfuerzo high · ⏱ 18s
- **Herramientas:** Bash ×1
- **Tokens:** entrada 2 · cache leída 318.6k · cache escrita 4.1k · salida 534 · hit 99%

<details><summary>Respuesta</summary>

El reinicio funcionó:
- **Hook de DEV-LOG:** registró la reanudación de la sesión con el estado del caché ("probablemente vigente, contexto de 319k tokens") y tu "Continua" quedó como #5.
- **graft:** sus herramientas MCP ya aparecen en esta sesión.
- **prompt-cache-control:** desde acá no puedo comprobar que cargó; si ves el medidor del caché sobre el prompt, está activo.

Antes de arrancar la constitución hay que subir el esfuerzo. El "max" de Opus 5.5 que pusiste con `/model` valía solo para la sesión anterior, y al reiniciar volvió al valor por defecto. Las etapas de planificación las acordamos en Opus 5.5 Max: ejecuta `/model`, elige Opus 5.5 con esfuerzo **max** (o usa `/effort max`) y escríbeme "continúa".

Con eso armo el bloque de constitución: `specs/mission.md`, `specs/tech-stack.md`, `specs/roadmap.md` y los primeros ADL (monorepo con 2 apps, stack, SQLite y auth simulada).

</details>

### #6 · 🧑 Usuario
> continua

#### 🤖 Claude · `claude-opus-5-5` · esfuerzo max · ⏱ 10m 0s
- **Herramientas:** Bash ×9 · Write ×9 · Edit ×5 · Read ×2
- **Archivos modificados:** `specs/mission.md`, `specs/tech-stack.md`, `specs/roadmap.md`, `.design-logs/ADL-001-two-apps-openapi-contract.md`, `.design-logs/ADL-002-fastapi-sqlmodel-backend.md`, `.design-logs/ADL-003-sqlite-mvp-postgres-path.md`, `.design-logs/ADL-004-react-vite-spa.md`, `.design-logs/ADL-005-simulated-auth-signed-token.md`, `.design-logs/ADL-006-docker-compose-same-origin.md`, `DECISIONS.md`, `AI-USAGE.md`
- **Tokens:** entrada 28 · cache leída 5.1M · cache escrita 63.4k · salida 53.4k · hit 99%

<details><summary>Respuesta</summary>

El bloque **Constitución** está terminado. Espero tu aprobación para hacer commit, push y abrir el PR de la Fase 1.

**Qué incluye**
- **`specs/mission.md`:** el problema, los dos actores, el flujo principal y una propuesta de ciclo de vida con 5 estados: Abierto, En progreso, En espera, Resuelto y Cerrado. Incluye también el alcance del MVP frente a lo diferido y 6 métricas de éxito.
- **`specs/tech-stack.md`:** arquitectura de las 2 apps, el stack con su porqué, el modelo de datos resumido, los 12 endpoints, los flujos de procesamiento, la paleta y los tokens del droide astromecánico, la estrategia de testing y las reglas de seguridad.
- **`specs/roadmap.md`:** 10 fases, cada una con su rama y su PR. La 2 es la especificación y el plan, de la 3 a la 8 va la implementación (una fase por user story), la 9 es el empaquetamiento y la 10 la escalabilidad.
- **6 ADL en `.design-logs/`:**
  - dos apps unidas por el contrato OpenAPI;
  - FastAPI con SQLModel;
  - SQLite con camino a PostgreSQL;
  - una SPA en React y Vite;
  - ingreso simulado con token firmado;
  - Docker Compose con nginx de proxy.
- **`DECISIONS.md`:** nuevas secciones de arquitectura (enlazada a los ADL) y de deuda técnica asumida.
- **`AI-USAGE.md`:** registra este bloque y el uso de context7.

**Checkpoint**
- No hay código, así que el lint, los tests y deckard no aplican en este bloque.
- Los ADL quedaron creados.
- Los 5 diagramas Mermaid renderizan sin errores (los validé con mermaid-cli y revisé visualmente los dos más densos).
- Ningún enlace entre documentos quedó roto.

**Decisiones que tomé yo y conviene que revises**
- **Versiones:** Python 3.14, la vigente con soporte amplio.
- **Web:** TanStack Query para refrescar datos y CSS Modules con tokens propios, en vez de Tailwind.
- **Cobertura mínima:** 90 % en la API y 70 % en la web. La API concentra las reglas de negocio y la web solo refleja lo que la API permite.
- **Acciones de cada ticket:** la API entrega las acciones permitidas para quien lo consulta, así la web no duplica la máquina de estados.
- **SLA:** su estado (en plazo, por vencer o vencido) se calcula al leer el ticket, no se guarda.

Tres puntos quedan abiertos para la etapa Clarify de la especificación: quién define la prioridad, si "En espera" pausa el SLA, y cómo funcionan el cierre y la reapertura.

**Commits que propongo en `phase/01-setup-constitution`**
1. `docs(constitution): agrega misión, stack y roadmap`
2. `docs(adl): registra ADL-001 a ADL-006`
3. `docs: actualiza DECISIONS, AI-USAGE y DEV-LOG`

Después el push y el **PR "Fase 1: setup y constitución"** hacia `main`, creado con la cuenta `sebastianms`. ¿Apruebas?

</details>

### #7 · 🧑 Usuario
> baja la cobertura a 80%, apliquemos ley de pareto...80/20, con 80% total pero con 90% de coverage en el flujo critico de la app.

#### 🤖 Claude · `claude-opus-5-5` · esfuerzo max · ⏱ 1m 25s
- **Herramientas:** Edit ×6 · Write ×1 · Bash ×1
- **Archivos modificados:** `specs/tech-stack.md`, `CLAUDE.md`, `.design-logs/ADL-007-pareto-coverage-gates.md`, `specs/roadmap.md`, `DECISIONS.md`, `AI-USAGE.md`
- **Tokens:** entrada 8 · cache leída 1.6M · cache escrita 9.6k · salida 8.9k · hit 99%

<details><summary>Respuesta</summary>

Listo: la cobertura queda en **80 % total y 90 % en el flujo crítico**.

**Cómo quedó**
- **`specs/tech-stack.md`:** la tabla de gates de cobertura dice qué se mide y dónde.

  | Alcance | Meta | Medición |
  |---|---|---|
  | Total de cada app | ≥ 80 % | pytest-cov con `--cov-fail-under=80`; umbral global en Vitest |
  | Flujo crítico de la API: `tickets/`, `sla/`, `audit/` y la autorización de `identity/` | ≥ 90 % | Segundo reporte limitado a esas rutas |
  | Flujo crítico de la web: `src/features/` | ≥ 90 % | Umbral por glob en Vitest |

- **`CLAUDE.md`:** el checkpoint de cada bloque exige ambos umbrales, así que los subagentes de coding no pueden cerrar un bloque por debajo.
- **ADL-007:** registra la decisión de Pareto, las alternativas descartadas (90 % parejo, y el 90/70 que propuse antes) y la regla de no escribir tests solo para subir el número.
- **`DECISIONS.md`:** nueva sección "Estrategia de calidad", que alimenta el entregable 4 del enunciado.
- **`AI-USAGE.md`:** tu cambio quedó como intervención del usuario.

Revisé que no quedara ninguna mención al 90/70 anterior fuera del registro histórico de DEV-LOG, y que todos los enlaces sigan funcionando.

**Commits que propongo en `phase/01-setup-constitution`:**
1. `docs(constitution): agrega misión, stack y roadmap`
2. `docs(adl): registra ADL-001 a ADL-007`
3. `docs: actualiza CLAUDE.md, DECISIONS, AI-USAGE y DEV-LOG`

Después hago el push y abro el **PR "Fase 1: setup y constitución"** hacia `main`. ¿Apruebas?

</details>

### #8 · 🧑 Usuario
> aprobado

