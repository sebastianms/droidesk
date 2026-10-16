# ADL-005: Ingreso simulado con usuarios precargados y token firmado

**Fecha:** 2026-10-16
**Estado:** Activo
**Área:** Seguridad
**Autor:** Usuario + AI Session

---

## Contexto

La autenticación puede ser simulada, pero el MVP necesita al menos dos perfiles con vistas distintas, y la API debe saber en cada request quién actúa para autorizar y registrar el historial. A escala, la organización usaría su propio proveedor de identidad.

---

## Decisión

Ingreso sin contraseña: la pantalla de ingreso lista los usuarios precargados y, al elegir uno, la API emite un JWT firmado (HS256) con su `sub` y una expiración de 8 horas. En cada request, la API valida el token, carga al usuario desde la base de datos y autoriza según su rol (`requester` o `agent`) mediante dependencias. El secreto lo genera `setup.sh`.

---

## Justificación

El token Bearer tiene la misma forma que tendrá con SSO u OIDC: al escalar solo cambia quién lo emite, no cómo lo consume la API. Leer el rol desde la base de datos evita confiar en datos del cliente. No gestionar contraseñas mantiene el MVP fuera de un problema que no aporta al enunciado.

---

## Consecuencias

### ✅ Positivas
- Frontera de autorización real y testeable en cada endpoint.
- El historial siempre tiene un autor confiable.
- Camino directo a SSO u OIDC.

### ⚠️ Trade-offs aceptados
- Cualquiera puede ingresar como cualquier usuario: válido solo para el MVP y la demo. Es deuda técnica consciente.
- Sin revocación de tokens antes de que expiren.

---

## Alternativas Consideradas

| Alternativa | Razón de descarte |
|-------------|-------------------|
| Header `X-User-Id` sin firma | No hay frontera: cualquier cliente cambia de identidad con un header; no se parece al modelo final |
| Usuario y contraseña con hash | Gestión de credenciales y recuperación fuera del alcance del enunciado |
| SSO u OIDC real | Requiere un proveedor externo; se contempla en el plan de escalamiento |

---

## Decisiones Relacionadas
- [ADL-002](ADL-002-fastapi-sqlmodel-backend.md): la autorización se implementa con dependencias de FastAPI.
- [ADL-004](ADL-004-react-vite-spa.md): guardas de ruta por rol en la web.

---

## Notas para el AI (Memoria Técnica)
- La autorización usa el rol del usuario en la base de datos, nunca un rol enviado por el cliente.
- El solicitante solo puede ver y comentar sus propios tickets: verifícalo en la API, no solo en la web.
- No hardcodees el secreto del token ni lo subas al repo: viene de `DROIDESK_JWT_SECRET`.
- No agregues contraseñas ni registro de usuarios: el siguiente paso es SSO, no credenciales propias.
