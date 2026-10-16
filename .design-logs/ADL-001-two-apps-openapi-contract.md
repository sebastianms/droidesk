# ADL-001: Monorepo con dos aplicaciones independientes unidas por un contrato OpenAPI

**Fecha:** 2026-10-16
**Estado:** Activo
**Área:** Arquitectura
**Autor:** Usuario + AI Session

---

## Contexto

El repositorio debe contener el front y el back, pero no como un monolito: deben tratarse como aplicaciones diferentes, modulares o federadas. Se evaluaron con el usuario tres formas: dos apps (API y web), una API con dos frontends (uno por perfil) y micro-frontends federados con Module Federation. La regla del proyecto es "Less is More".

---

## Decisión

Un monorepo con `apps/api` y `apps/web`, independientes en dependencias, build, tests, Dockerfile y CI. Se comunican solo por HTTP, mediante `contracts/openapi.json`: lo genera la API, se versiona en el repo y la web genera sus tipos desde ese archivo. La API se organiza en módulos de dominio: `identity`, `tickets`, `audit` y `sla`.

---

## Justificación

Da una separación real entre aplicaciones, con despliegue independiente, sin la complejidad de build y versionado de Module Federation. El contrato explícito convierte cualquier cambio incompatible en un error de compilación de la web y en una diferencia que detecta el CI. Las dos vistas por perfil caben en una sola SPA con rutas por rol, sin duplicar setup ni componentes.

---

## Consecuencias

### ✅ Positivas
- Cada app se construye, prueba y despliega por separado; el CI usa filtros de ruta por app.
- Tipos de punta a punta: un campo renombrado en la API rompe el build de la web, no producción.
- Los módulos de dominio de la API se pueden extraer como servicios si el sistema crece.

### ⚠️ Trade-offs aceptados
- El contrato se regenera y se commitea junto con cada cambio de endpoint.
- Algunas validaciones de UX se repiten en la web (largo de un campo); la regla vale solo en la API.

---

## Alternativas Consideradas

| Alternativa | Razón de descarte |
|-------------|-------------------|
| API + dos frontends (portal y consola) | Duplica setup, build y componentes compartidos para dos vistas que caben en una SPA |
| Micro-frontends federados (Module Federation) | Complejidad de build, versionado y orquestación desproporcionada para un MVP |
| FastAPI sirviendo templates o la SPA | Es un monolito: incumple el requisito |

---

## Decisiones Relacionadas
- [ADL-002](ADL-002-fastapi-sqlmodel-backend.md): stack de la API, que genera el contrato.
- [ADL-004](ADL-004-react-vite-spa.md): stack de la web, que lo consume.
- [ADL-006](ADL-006-docker-compose-same-origin.md): cada app tiene su propia imagen.

---

## Notas para el AI (Memoria Técnica)
- No importes código entre `apps/api` y `apps/web`, ni crees paquetes compartidos: el único punto de unión es `contracts/openapi.json`.
- Todo cambio de endpoint actualiza `contracts/openapi.json` y los tipos de la web en el mismo commit.
- Las reglas de negocio viven solo en la API; la web muestra lo que la API permite.
- No propongas Module Federation ni un tercer frontend sin un ADL nuevo que lo justifique.
