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

