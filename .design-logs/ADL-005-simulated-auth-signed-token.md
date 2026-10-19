# ADL-005: Ingreso simulado con usuarios precreados y token firmado

**Fecha:** 2026-10-16
**Estado:** Activo (revisado el 2026-10-17)
**Área:** Seguridad
**Autor:** Usuario + AI Session

---

## Contexto

La autenticación puede ser simulada, pero el MVP necesita al menos dos perfiles con vistas distintas, y la API debe saber en cada request quién actúa para autorizar y registrar el historial. A escala, la organización usaría su propio proveedor de identidad.

---

## Decisión

Login simulado: el formulario pide usuario y contraseña. Los usuarios vienen precreados por perfil, y la API acepta cualquier contraseña de un usuario existente; uno inexistente recibe 401 y nunca se crea. Un ícono "?" muestra los usuarios de demo y su perfil, desde `GET /api/v1/auth/users`. La contraseña se ignora y nunca se guarda ni se registra. Luego la API emite un JWT firmado (HS256) con su `sub` y una expiración de 8 horas. En cada request, la API valida el token, carga al usuario desde la base de datos y autoriza según su rol (`requester` o `agent`) mediante dependencias. El secreto lo genera `setup.sh`.

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
| Elegir un usuario de una lista, sin contraseña (primera versión) | El usuario la rechazó: debe existir un login, y la autenticación simulada significa que cualquier usuario y contraseña responden OK |
| Elegir el rol en cada login, también para usuarios existentes | El cliente decidiría el rol de alguien que ya existe |
| Crear el usuario en el login con el perfil elegido (segunda versión) | El usuario la rechazó: crearía usuarios sin límite. Se prefieren usuarios precreados por perfil y una ayuda que los liste |
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
- No valides ni guardes contraseñas, y no crees usuarios desde la app: el login simulado acepta cualquier contraseña de un usuario precreado. El siguiente paso es SSO, no credenciales propias.
- La contraseña nunca debe aparecer en una respuesta, en un log ni en la base, tampoco en los errores 422.

---

## Extensión 2026-10-17 · Fundaciones (Fase 3)

- **Token**: JWT HS256 con `sub`, `iat` y `exp` obligatorios, firmado con `DROIDESK_JWT_SECRET` (al menos 32 bytes), y el reloj se inyecta para los tests. Un token inválido o vencido, o un usuario que ya no existe, responde 401.
- **Validación de la sesión en la web**: no se consulta `/me` en cada navegación. El middleware valida `expires_at` en el cliente, y el cliente HTTP, ante un 401, borra la sesión y recarga en `/login`, salvo que ya esté ahí, para no entrar en un bucle. Así se cierra el pendiente de research.
- **Caché acotada a la sesión**: el ingreso y la salida llaman a `queryClient.clear()`, para que un perfil nunca vea datos en caché del anterior en la misma pestaña.
- **Leer la sesión no tiene efectos**: una sesión vencida se ignora al leerla y se borra solo al salir, al recibir un 401 o al ingresar con otro perfil.
- **Datos de demo**: 7 usuarios (4 solicitantes y 3 agentes, con `username` como `ana.rojas` o `elena.vidal`), 5 categorías y las 4 políticas de SLA. Se cargan una sola vez (en la Fase 9 el flag pasó a ser `DROIDESK_MODE`; ver la extensión del 2026-10-19), si `DROIDESK_SEED_DEMO_DATA=true` y la base está vacía.

---

## Revisión 2026-10-17 · Login con credenciales libres (decisión del usuario)

> Reemplazada por la segunda revisión (abajo): ya no se crean usuarios ni hay selector de perfil.

Al revisar la app, el usuario pidió que exista un login y aclaró que la autenticación simulada significa que el proceso responde OK sin importar el usuario ni la contraseña. Se reemplazó la lista de usuarios por un formulario de usuario, contraseña y perfil:
- `POST /api/v1/auth/login` recibe `{username, password, role}`. El `username` se normaliza (se recortan los espacios y pasa a minúsculas). Si dos logins crean el mismo usuario a la vez, el conflicto por la restricción de unicidad se resuelve releyendo el usuario existente.
- Un usuario nuevo se crea con el perfil elegido. Uno existente entra con su perfil guardado: el rol de alguien que ya existe nunca lo decide el cliente.
- La contraseña se ignora y no se guarda, no se registra en logs ni se devuelve en las respuestas.
- `GET /api/v1/auth/users` se eliminó: ya no hacía falta y exponía la lista de usuarios sin autenticación.
- `users` gana la columna `username`, única. La migración 0001 se corrigió en su lugar, porque aún no estaba publicada.

### Segunda revisión 2026-10-17 · Usuarios precreados y ayuda en el login

Al revisar la primera revisión, el usuario pidió no crear usuarios sin límite, tener usuarios precreados por perfil y mostrar en el login un ícono "?" con los usuarios y sus perfiles, para efectos de demo:
- `POST /api/v1/auth/login` recibe solo `{username, password}`. Si el usuario no existe, responde 401 `not_authenticated` con un mensaje que remite a la ayuda; nunca crea usuarios. Se eliminan el selector de perfil y la lógica de creación.
- `GET /api/v1/auth/users` vuelve como endpoint público, pero solo con `username`, nombre y perfil (`DemoUser`, sin email ni id). Alimenta la ayuda, así la web no duplica los datos del seed.
- Al elegir un usuario en la ayuda, se completa el campo Usuario.
- Siguen vigentes la normalización del `username`, la columna `username` única y el 422 sin `input`.

---

## Extensión 2026-10-19 · Modos de arranque Demo y Vacío (Fase 9, a pedido del usuario)

Al sumar los tickets de ejemplo (T058), responder "no" a los datos de demo dejaba una app sin usuarios con quienes ingresar. Al revisarlo, el usuario pidió dos modos: uno Demo, con datos para recorrer las funcionalidades, y otro vacío, solo con los usuarios.
- **Base**: los 7 usuarios de demo, las 5 categorías y las 4 políticas de SLA se cargan **siempre** que la base de datos está vacía. Con el ingreso simulado y sin administración, sin ellos la app no sirve.
- **`DROIDESK_MODE`** reemplaza al booleano `DROIDESK_SEED_DEMO_DATA`:
  - `demo`, el valor por defecto, carga además 9 tickets de ejemplo en distintos estados, con comentarios, una respuesta citada, un ajuste de prioridad y su historial;
  - `empty` deja la base solo con los usuarios y los catálogos;
  - un valor inválido impide que la API arranque.
- **El modo no borra datos**: los tickets de ejemplo se cargan solo mientras no exista ningún ticket. Pasar de Vacío a Demo los agrega si todavía no se creó ninguno, y pasar de Demo a Vacío conserva lo que hay. `setup.sh` avisa si el volumen ya existe y explica cómo empezar de cero (`docker compose down -v`).
- **Los tickets se reproducen con `TicketService`** y un reloj del seed que se coloca en el pasado y avanza paso a paso (`demo_tickets.py`). Así, el historial, el SLA y los contadores son los mismos que dejaría una persona real.
  - Cada ticket tiene una antigüedad relativa a la carga, elegida para que su estado de SLA no dependa del día ni de la hora: el vencido tiene 6 días corridos, y ninguno queda "por vencer".
