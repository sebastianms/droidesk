# Research: Ticketing MVP

**Feature**: `001-ticketing-mvp` · **Fecha**: 2026-10-16
**Método**: documentación vigente vía context7 (IDs en cada sección), registros de npm y PyPI, y prototipos descartables de la API y de la web, construidos y probados (lint, tipos, tests con cobertura, build e imágenes Docker).

## Hallazgos que cambiaron supuestos

| # | Hallazgo | Decisión |
|---|---|---|
| 1 | TypeScript 7.0 (port nativo) rompe `openapi-typescript` y `typescript-eslint`, que dependen de la API JS del compilador | Se fija `typescript ~6.0.3`, compatible a nivel de API con 5.9 |
| 2 | `openapi-typescript` 7.13 declara `peer typescript ^5.x`: `npm install` falla aun con TS 6 | `overrides` en `package.json` (probado) |
| 3 | El template `react-ts` de Vite ya no trae ESLint, sino Oxlint | Se adopta Biome (lint y formato en un binario) |
| 4 | React Router 8 eliminó `react-router-dom` | Solo `react-router`; guardas por rol con middleware |
| 5 | `baseUrl: "/api"` duplica el prefijo si las rutas del contrato ya empiezan con `/api` | Las rutas del contrato incluyen `/api`; el cliente usa el origen como `baseUrl` |
| 6 | El `TestClient` de Starlette 1.8 prefiere `httpx2`: con `httpx` emite un warning que rompe pytest con `filterwarnings = error` | `httpx2` como dependencia de desarrollo |
| 7 | SQLModel ≥ 0.0.45 mapea `datetime` a `UTCDateTime`: exige fechas con zona y devuelve UTC | Refuerza [ADL-003](../../.design-logs/ADL-003-sqlite-mvp-postgres-path.md): una fecha sin zona es un error |
| 8 | `PRAGMA foreign_keys=ON` hace fallar las migraciones batch de Alembic | Las FK se activan solo en el engine de la app, no en el de Alembic |
| 9 | `astral-sh/setup-uv` no publica tags mayores flotantes | Las acciones de GitHub se fijan por SHA |

## API (`apps/api`)

### Versiones

| Paquete | Versión | Motivo |
|---|---|---|
| Python (imagen) | `python:3.14.8-slim-trixie` | Python 3.14 con SQLite 3.46 (soporta `RETURNING`) |
| uv | 0.13.1 | Gestor de dependencias; en Docker se copia desde `ghcr.io/astral-sh/uv:0.13.1` |
| fastapi | 0.143.3, sin `[standard]` | Versión vigente sin extras innecesarios |
| sqlmodel | 0.0.48 (tope `<0.0.49`) | Primera versión compatible con SQLAlchemy 2.1; una 0.0.x puede romper |
| sqlalchemy | 2.1.5 (respaldo 2.0.55) | Wheels para Python 3.14 |
| pydantic / pydantic-settings | 2.14.1 / 2.16.0 | Validación y configuración con prefijo `DROIDESK_` |
| alembic | 1.20.0 | Plantilla `pyproject`, modo batch y `alembic check` |
| uvicorn | 0.54.0 | Servidor ASGI, un solo proceso |
| pyjwt | 2.15.1 | Token HS256; las versiones 2.13 a 2.15 corrigen avisos de seguridad |
| tzdata | 2026.5 | Reglas de zona horaria idénticas en desarrollo, CI e imagen (`PYTHONTZPATH=""`) |
| httpx2 *(dev)* | 2.13.1 | Cliente del `TestClient` |
| pytest / pytest-cov | 9.1.1 / 7.1.0 | Configuración nativa en `[tool.pytest]` y los dos gates de cobertura |
| ruff / mypy | 0.17.1 / 2.4.0 | Lint, formato y tipado estricto con el plugin de pydantic |

### Decisiones

| ID | Decisión | Por qué | Alternativa descartada |
|---|---|---|---|
| D-B1 | Configuración con `pydantic-settings`, prefijo `DROIDESK_` y `get_settings()` cacheado | Valida los valores al iniciar y mantiene un solo lugar de configuración | `os.environ` disperso |
| D-B2 | `build_engine(url)` único para la app y los tests: `check_same_thread=False` y pragmas `foreign_keys=ON` y `journal_mode=WAL` mediante un listener **solo en ese engine**; sesión por request; el commit lo hace el servicio | Las FK protegen la integridad; un listener global rompería las migraciones (hallazgo 8) | Listener sobre la clase `Engine` |
| D-B3 | Enums `StrEnum` con miembros en mayúscula y valores en minúscula (`OPEN = "open"`), guardados como texto (`native_enum=False`, `values_callable`) | La API y la base hablan el mismo código del contrato; sin enums nativos que compliquen PostgreSQL | Guardar el nombre del miembro, que es el default de SQLAlchemy |
| D-B4 | Tomar y cancelar con un `UPDATE ... WHERE status = 'open' AND assignee_id IS NULL`, verificando `rowcount == 1` | Atómico sin locks explícitos. En una carrera de 16 hilos, repetida 5 veces, hubo exactamente un ganador | Leer y luego escribir, con riesgo de doble asignación |
| D-B5 | Jerarquía `DomainError` (código, mensaje y status) con un solo exception handler que responde `{code, message}`. Las rutas declaran `responses={4xx: {"model": ErrorBody}}` para que el OpenAPI tipifique los errores. 401 uniforme con `HTTPBearer(auto_error=False)` | Un solo formato de error, tipado hasta la web | El `HTTPException` suelto de FastAPI, que responde `{detail}` |
| D-B6 | El 422 de validación mantiene el formato estándar de FastAPI (`detail[]`) | Viene documentado y tipado en el OpenAPI sin código extra. La web valida antes de enviar y el 422 queda como red de seguridad | Un handler propio de 422, que dejaría el OpenAPI desalineado. *Fase 3*: se agregó un handler que conserva el esquema y solo quita `input`, que es opcional, para no devolver la contraseña ([ADL-002](../../.design-logs/ADL-002-fastapi-sqlmodel-backend.md)) |
| D-B7 | JWT con `sub` (string), `iat` y `exp` de 8 h; `algorithms=["HS256"]` y `require` explícitos; se captura `InvalidTokenError`. Secreto de al menos 32 bytes (`openssl rand -hex 32` en `setup.sh`) | Cierra `alg=none` y los claims faltantes; una clave corta emite warning | Sesiones en el servidor |
| D-B8 | Alembic con la plantilla `pyproject`, `render_as_batch=True`, naming convention en `SQLModel.metadata`, `import sqlmodel.sql.sqltypes` en la plantilla de migraciones y ruff como post-write hook. El entrypoint del contenedor corre `alembic upgrade head` y después `exec uvicorn`. En CI corren `alembic upgrade head` y `alembic check` | Migraciones reproducibles; `alembic check` detecta que el modelo diverge de las migraciones | `create_all` |
| D-B9 | Tiempo hábil con funciones puras propias sobre `zoneinfo` ([ADL-009](../../.design-logs/ADL-009-sla-business-time.md)) | Sin dependencias, con bordes exhaustivos en los tests | `businesstimedelta` (abandonada, usa pytz), `workalendar` (trabaja por días), pandas (pesado) |
| D-B10 | La autorización vive en `identity/authorization.py` | El gate de 90 % del flujo crítico mide archivos concretos | Dispersar los chequeos de rol |
| D-B11 | `scripts/export_openapi.py`, fuera de `src/`, escribe `contracts/openapi.json`. Importar la app no exige secretos ni toca la base de datos | El CI puede regenerar el contrato y compararlo | Generar el contrato a mano |

## Web (`apps/web`)

### Versiones

| Paquete | Versión | Motivo |
|---|---|---|
| Node (imagen) | `node:24-alpine` (≥ 24.15) | jsdom 30 y React Router 8 elevan el piso de Node |
| create-vite | 9.2.1 | `npm create vite@9.2.1 apps/web -- --template react-ts --no-interactive` |
| vite / @vitejs/plugin-react | 8.3.4 / 6.1.2 | Rolldown/Oxc; React Refresh sin Babel |
| react / react-dom | 19.3.1 | React Router 8 exige ≥ 19.2.7 |
| typescript | ~6.0.3 | Hallazgo 1 |
| react-router | 8.4.0 | Modo data, sin `react-router-dom` |
| @tanstack/react-query | 5.104.3 | Estado de servidor |
| openapi-fetch / openapi-react-query | 0.17.0 / 0.5.4 | Cliente y hooks tipados; se evita la 1.0.0, deprecada |
| openapi-typescript | 7.13.0 + `overrides` | Hallazgo 2 |
| @biomejs/biome | 2.5.15 | Hallazgo 3 |
| vitest / @vitest/coverage-v8 | 5.0.5 / 5.0.5 | Deben tener la misma versión exacta |
| jsdom | 30.1.3 | Más fiel que happy-dom |
| @testing-library/react / dom / jest-dom / user-event | 16.3.3 / 10.4.2 / 7.0.1 / 14.6.8 | `dom` es peer obligatorio de RTL 16 |
| nginx (imagen) | `nginx:1.30-alpine` | Rama estable |

### Decisiones

| ID | Decisión | Por qué | Alternativa descartada |
|---|---|---|---|
| D-F1 | Scaffold con create-vite en modo no interactivo; se quitan `oxlint` y sus SVG de ejemplo | Partir del template oficial vigente | Configurar Vite a mano |
| D-F2 | TypeScript 6 estricto. Al tsconfig del template se agrega `strict` explícito; los defaults de TS 6 obligan a listar `types` | Migrar a TS 7 será solo cambiar la versión cuando las herramientas lo soporten | TS 7 junto a TS 6 (dos compiladores) |
| D-F3 | Biome: `preset: recommended`, `useComponentExportOnlyModules`, formato con comillas simples y sin punto y coma; el gate es `biome ci --error-on-warnings .` | 2 paquetes contra ~140 de ESLint + Prettier; incluye `noDangerouslySetInnerHtml`, que hace cumplir ADL-004 | ESLint 10 + typescript-eslint (no soporta TS 7, mucha configuración); Oxlint + oxfmt (formateador pre-1.0) |
| D-F4 | React Router en modo data (`createBrowserRouter` + `RouterProvider` desde `react-router/dom`), layouts sin `path` y guardas `requireSession` / `requireRole` como middleware | El middleware corre en cada navegación; un componente guard renderiza antes de redirigir | Guardas en loaders o en componentes |
| D-F5 | TanStack Query con `openapi-react-query`: keys tipadas `[método, ruta, init]`, `staleTime` de 30 s y `retry: 1`. Las mutaciones invalidan el prefijo `['get', '/api/v1/tickets']` y el detalle; al cerrar sesión se llama `queryClient.clear()` | Sin fábricas de keys ni wrappers propios; no quedan datos de otro usuario en caché | Hooks hechos a mano sobre openapi-fetch |
| D-F6 | Cliente `openapi-fetch` con `baseUrl: window.location.origin`, un `fetch` envuelto (para poder mockearlo en tests) y un middleware Bearer. El middleware `onResponse` cierra la sesión ante un 401 | Hallazgo 5; tests deterministas | `baseUrl: "/api"` |
| D-F7 | La sesión (`token` + `user`) vive en `sessionStorage` | Sobrevive a un reload y se borra al cerrar la pestaña. El riesgo de XSS se mitiga con CSP y sin renderizar HTML | `localStorage` (persiste entre sesiones); memoria (se pierde al recargar) |
| D-F8 | `schema.d.ts` se genera con `npm run gen:api` desde `../../contracts/openapi.json` y se commitea; el CI verifica que no cambió | El build de Docker no depende de la API (ADL-001) | Generarlo durante el build |
| D-F9 | Vitest con jsdom, `globals: false` y `cleanup` explícito. Coverage v8 con `include` explícito y umbrales `{ lines: 80, 'src/features/**': { lines: 90 } }` | Gates de [ADL-007](../../.design-logs/ADL-007-pareto-coverage-gates.md) verificados: un archivo de `features/` sin tests hace fallar la suite aunque el global pase | happy-dom |
| D-F10 | nginx: SPA con `try_files`, proxy de `/api/` sin reescritura, assets con caché de 1 año, `index.html` sin caché y headers de seguridad (CSP `default-src 'self'`, `nosniff`, `DENY`, `Referrer-Policy` y `Permissions-Policy`) | Mismo origen (ADL-006) y una superficie mínima | Servir la SPA desde la API |

## Infraestructura y CI

| ID | Decisión | Por qué |
|---|---|---|
| D-I1 | Imagen de la API multi-stage con uv: `uv sync --locked --no-dev`, venv copiado a una imagen sin uv, usuario no root (uid 999), healthcheck en Python contra `/api/health` y entrypoint con `exec`. Pesa 169 MB, probada | Reproducible, liviana y con un apagado limpio |
| D-I2 | Imagen de la web multi-stage `node:24-alpine` → `nginx:1.30-alpine`. Pesa 69 MB, probada | Solo estáticos y nginx en runtime |
| D-I3 | En compose, `web` depende de `api` con `condition: service_healthy` | nginx no arranca si no resuelve el upstream |
| D-I4 | Un workflow por app, `api.yml` y `web.yml`, con filtro de rutas (cada uno incluye `contracts/**`), `permissions: contents: read` y acciones fijadas por SHA | Las apps también son independientes en CI. Los checks no se marcan como requeridos, porque un workflow que se salta por filtro queda en "Pending" |
| D-I5 | El CI de la API regenera `contracts/openapi.json` y falla si hay diferencias; el CI de la web regenera `schema.d.ts` y falla si hay diferencias | El contrato nunca diverge sin que se note |

## Notas para la implementación

- **rtk**: el hook interpreta `npm run lint` como ESLint y oculta la salida real de Biome. Para ver la salida cruda, usar `rtk proxy npm run lint`.
- **Tests de la API**: `filterwarnings = ["error"]` (un warning es una falla), `engine.dispose()` en los fixtures y un secreto de prueba de al menos 32 bytes.
- **Tests de la web**: un `QueryClient` nuevo por test con `retry: false`; el router de prueba es `createMemoryRouter`.
- **Riesgos del ecosistema**: SQLAlchemy 2.1 y su soporte en SQLModel tienen pocos días (respaldo: 2.0.55). `openapi-react-query` está en 0.x.
- **Pendiente de verificar al implementar**:
  - ~~la CSP en un navegador real~~: verificada en el Setup, con Chrome headless sobre la imagen de nginx y sin violaciones;
  - ~~el workflow ejecutado en GitHub~~: `api.yml` y `web.yml` en verde en la primera corrida (setup-uv resuelve uv 0.13.1);
  - ~~validar la sesión contra `/me` dentro del middleware~~: descartado en Foundational. La sesión se valida por `expires_at` y el 401 del cliente HTTP la cierra ([ADL-005](../../.design-logs/ADL-005-simulated-auth-signed-token.md)).

## Anexo: configuraciones de referencia

Verificadas en los prototipos; los subagentes de coding las usan como punto de partida.

### `apps/api/pyproject.toml` (calidad)

```toml
[tool.pytest]
minversion = "9.0"
strict = true
testpaths = ["tests"]
addopts = ["--cov", "--cov-report=term-missing:skip-covered", "--cov-fail-under=80"]
filterwarnings = ["error"]

[tool.coverage.run]
source_pkgs = ["droidesk_api"]

[tool.coverage.report]
exclude_also = ["if TYPE_CHECKING:"]

[tool.ruff.lint]
extend-select = ["FAST", "DTZ", "N", "ERA", "PLR2004", "C90", "ARG", "T20", "S", "PT"]

[tool.ruff.lint.mccabe]
max-complexity = 8

[tool.ruff.lint.per-file-ignores]
"tests/**" = ["S101", "PLR2004", "ARG"]

[tool.mypy]
strict = true
warn_unreachable = true
plugins = ["pydantic.mypy"]
```

Gate del flujo crítico, desde `apps/api`:

```bash
uv run pytest   # gate total: 80 %
uv run coverage report --fail-under=90 \
  --include='src/droidesk_api/tickets/*,src/droidesk_api/sla/*,src/droidesk_api/audit/*,src/droidesk_api/identity/authorization.py'
```

### Toma atómica (SQLModel)

```python
def assign_if_open(session: Session, ticket_id: int, agent_id: int, now: datetime) -> bool:
    result = session.exec(
        update(Ticket)
        .where(col(Ticket.id) == ticket_id, col(Ticket.status) == TicketStatus.OPEN, col(Ticket.assignee_id).is_(None))
        .values(status=TicketStatus.IN_PROGRESS, assignee_id=agent_id, updated_at=now)
    )
    return result.rowcount == 1  # 0: lo tomó otro o fue cancelado → 409
```

### `apps/web/vite.config.ts` (tests y cobertura)

```ts
export default defineConfig({
  plugins: [react()],
  server: { proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } } },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/**/*.test.{ts,tsx}', 'src/test/**', 'src/api/schema.d.ts', 'src/main.tsx'],
      thresholds: { lines: 80, 'src/features/**': { lines: 90 } },
    },
  },
})
```

### `apps/web/biome.json`

```json
{
  "files": { "includes": ["**", "!src/api/schema.d.ts", "!!dist", "!!coverage"] },
  "formatter": { "indentStyle": "space", "lineWidth": 120 },
  "linter": { "rules": { "preset": "recommended", "style": { "useComponentExportOnlyModules": "error" } } },
  "javascript": { "formatter": { "quoteStyle": "single", "semicolons": "asNeeded" } },
  "css": { "parser": { "cssModules": true } },
  "assist": { "actions": { "source": { "organizeImports": "on" } } }
}
```

### Guardas por rol (React Router 8)

```tsx
export const requireRole = (role: Role): MiddlewareFunction => () => {
  const session = getSession()
  if (!session) throw redirect('/login')
  if (session.role !== role) throw redirect(homeFor(session.role))
}
```

### `apps/web/nginx.conf`

```nginx
server {
    listen 80;
    root /usr/share/nginx/html;
    server_tokens off;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-Frame-Options "DENY" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
    add_header Content-Security-Policy "default-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'" always;
    add_header Permissions-Policy "camera=(), microphone=(), geolocation=()" always;
    location /api/ {
        proxy_pass http://api:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    location /assets/ { expires 1y; }
    location / { try_files $uri /index.html; expires -1; }
}
```
