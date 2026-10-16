# ADL-003: SQLite en el MVP con un camino explícito a PostgreSQL

**Fecha:** 2026-10-16
**Estado:** Activo
**Área:** Base de Datos
**Autor:** Usuario + AI Session

---

## Contexto

El MVP debe usar una base de datos pequeña, como SQLite. El plan de escalamiento debe contemplar PostgreSQL para 50.000 tickets al mes y 5 áreas de soporte. El volumen del MVP es el de una organización de ~800 personas.

---

## Decisión

SQLite en un archivo dentro de un volumen Docker, con claves foráneas activadas y modo WAL. La conexión se configura con `DROIDESK_DATABASE_URL`. El código usa solo SQLAlchemy portable y el esquema se versiona con Alembic (modo batch para los cambios de tablas en SQLite). Migrar a PostgreSQL debe ser cambiar la URL, correr las migraciones y mover los datos.

---

## Justificación

Cero infraestructura adicional para el MVP y transacciones reales para escribir el ticket y su evento juntos. Mantener el código portable desde el día uno evita que la migración futura sea una reescritura.

---

## Consecuencias

### ✅ Positivas
- Arranque instantáneo y respaldo trivial (un archivo).
- El mismo esquema y las mismas migraciones sirven para PostgreSQL.

### ⚠️ Trade-offs aceptados
- Un solo escritor a la vez: suficiente para el MVP, no para la escala objetivo.
- Sin réplicas ni búsqueda de texto avanzada.
- SQLite no guarda zonas horarias: las fechas se normalizan a UTC en la aplicación.

---

## Alternativas Consideradas

| Alternativa | Razón de descarte |
|-------------|-------------------|
| PostgreSQL desde el inicio | Más infraestructura para el MVP; el requisito pide una base pequeña |
| Archivos JSON o planillas | Sin transacciones ni consultas: repetiría el problema que DroiDesk reemplaza |

---

## Decisiones Relacionadas
- [ADL-002](ADL-002-fastapi-sqlmodel-backend.md): SQLModel y Alembic son el puente entre motores.
- [ADL-006](ADL-006-docker-compose-same-origin.md): el archivo vive en un volumen nombrado.

---

## Notas para el AI (Memoria Técnica)
- No uses tipos, funciones ni SQL exclusivos de SQLite.
- Guarda y compara fechas siempre en UTC; conviértelas a hora local solo en la web.
- Todo cambio de esquema va en una migración de Alembic, nunca con `create_all` en producción.
- Las operaciones que modifican un ticket y su historial van en una sola transacción.
