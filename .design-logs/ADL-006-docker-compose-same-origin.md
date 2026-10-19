# ADL-006: Despliegue local con Docker Compose y proxy de mismo origen

**Fecha:** 2026-10-16
**Estado:** Activo
**Área:** Infraestructura
**Autor:** Usuario + AI Session

---

## Contexto

El setup debe ser un solo comando que levante todo con Docker y le pida al usuario la configuración necesaria. Las apps deben seguir siendo independientes ([ADL-001](ADL-001-two-apps-openapi-contract.md)), y la web necesita llamar a la API sin complicaciones de CORS.

---

## Decisión

Docker Compose con dos servicios. `api` corre uvicorn y, al iniciar, aplica las migraciones y carga los datos de demo según el modo de arranque. `web` es nginx: sirve el build de la SPA y hace de proxy de `/api` hacia `api`. SQLite vive en un volumen nombrado. `setup.sh` verifica Docker, pregunta la configuración, genera el secreto en `.env`, levanta todo y muestra las URLs y los usuarios de demo.

---

## Justificación

El navegador ve un único origen, así que no hay que configurar CORS ni exponer la API por separado. Cada app conserva su propia imagen y su propio ciclo de build. Un único script cumple el pedido de levantar todo con un comando.

---

## Consecuencias

### ✅ Positivas
- Una sola URL para el usuario y la API detrás del mismo origen.
- Las imágenes se pueden desplegar por separado más adelante.
- Los datos sobreviven a reinicios gracias al volumen.

### ⚠️ Trade-offs aceptados
- nginx es una pieza más que configurar en la imagen de la web.
- Migrar al iniciar la API sirve para una sola instancia; con varias réplicas debe pasar a un paso de despliegue.

---

## Alternativas Consideradas

| Alternativa | Razón de descarte |
|-------------|-------------------|
| Servir la SPA desde FastAPI | Acopla las apps y contradice ADL-001 |
| Vite dev server dentro de Docker | No es apto para producción |
| API expuesta aparte con CORS | Más configuración y superficie de error sin beneficio en el MVP |
| Kubernetes | Desproporcionado para un despliegue local |

---

## Decisiones Relacionadas
- [ADL-001](ADL-001-two-apps-openapi-contract.md): una imagen por app.
- [ADL-003](ADL-003-sqlite-mvp-postgres-path.md): el archivo de SQLite vive en un volumen.
- [ADL-004](ADL-004-react-vite-spa.md): la SPA usa una URL base relativa.

---

## Notas para el AI (Memoria Técnica)
- No habilites CORS abierto en la API: el mismo origen lo hace innecesario.
- En desarrollo, el proxy de Vite reemplaza a nginx; las llamadas siguen yendo a `/api` en el mismo origen.
- El único comando de arranque documentado es `./setup.sh`; no agregues pasos manuales al README.
- Con más de una réplica de la API, saca las migraciones del arranque.

---

## Extensión 2026-10-17 · Implementación del Setup (Fase 3)

La decisión de fondo no cambia. Se fijaron estos detalles al implementarla:
- **Compose**: el proyecto se llama `droidesk` y las imágenes, `droidesk-api:local` y `droidesk-web:local`, para cumplir la regla de tags de `CLAUDE.md`.
  - `api` no publica puertos: solo lo alcanza nginx.
  - `web` publica `${DROIDESK_WEB_PORT:-8080}:80` y espera a que `api` esté `healthy`, porque nginx resuelve `api` al arrancar.
  - `.env` es opcional (`env_file` con `required: false`); `.env.example` documenta las variables y el secreto queda vacío hasta que `setup.sh` lo genere.
- **API**:
  - imagen multi-stage con uv y usuario no root (uid 999), dueño de `/data`;
  - `HEALTHCHECK` en Python, sin curl;
  - uvicorn arranca con `--factory` sobre `create_app()`;
  - el entrypoint corre `alembic upgrade head` solo si existe `migrations/env.py`;
  - Alembic se configura en `pyproject.toml`, sin `alembic.ini`.
- **Web**:
  - nginx agrega CSP, `nosniff`, `X-Frame-Options`, `Referrer-Policy` y `Permissions-Policy` a nivel de `server`, nunca dentro de un `location`;
  - `/assets/` lleva caché larga e `index.html`, `no-cache`;
  - el proceso maestro de nginx corre como root y los workers como `nginx`, que es la imagen oficial sin cambios. Correr todo como no root exige cambiar el puerto interno a 8080 y queda como mejora.
- **CI**:
  - un workflow por app con filtro de rutas, runner `ubuntu-24.04` y acciones fijadas por SHA;
  - el gate del flujo crítico y `alembic check` se saltan (`if: hashFiles(...)`) mientras no existan sus archivos, y se activan solos cuando aparecen.

---

## Extensión 2026-10-19 · `setup.sh` (Fase 9)

- **Un solo comando**: `./setup.sh` verifica Docker, el daemon y Compose v2, y hace lo siguiente:
  - pregunta el puerto, la zona horaria, la jornada y el modo de arranque (Demo o Vacío, [ADL-005](ADL-005-simulated-auth-signed-token.md)), con un valor por defecto y validando cada respuesta;
  - avisa si el volumen de datos ya existe, porque cambiar de modo no borra los datos;
  - genera el secreto (`openssl rand -hex 32`, con respaldo en `/dev/urandom`) en un `.env` con permisos 600, sin mostrarlo nunca;
  - corre `docker compose up -d --build --wait`; si falla, muestra el log de la API;
  - muestra la URL, el modo y los usuarios de demo, que consulta a la API desde dentro del contenedor, así el host no necesita `curl` ni `jq`.
- **`.env` existente**: el script ofrece reutilizarlo, y en ese caso no regenera el secreto ni vuelve a preguntar.
- **`--yes`**: modo no interactivo para CI. Toma los valores de las variables de entorno o los de por defecto, y falla sin escribir `.env` si alguno es inválido.
- **Portabilidad**: bash 3.2 (macOS) y shellcheck sin hallazgos; CI corre shellcheck antes de levantar el stack.
- **SM-06**: con las imágenes base ya descargadas, el arranque desde cero toma unos 20 segundos. La descarga de las imágenes base depende de la red y no se midió.
- `COMPOSE_PROJECT_NAME` permite levantar un stack aislado (por ejemplo, `droidesk-test`) sin tocar el del usuario.
