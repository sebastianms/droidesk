# ADL-011: Escalar como monolito modular sobre PostgreSQL

**Fecha:** 2026-10-19
**Estado:** Activo
**Área:** Arquitectura
**Autor:** Usuario + AI Session (Fase 10)

---

## Contexto

El enunciado pide decir qué se rompería o rediseñaría para llegar a 50.000 tickets al mes y 5 áreas de soporte. [SCALABILITY.md](../SCALABILITY.md) estima la carga y compara tres estrategias, todas con PostgreSQL: A, monolito modular; B, celdas por área, y C, servicios por contexto con eventos. La carga es moderada (menos de una escritura por segundo en promedio). El cambio de fondo son las áreas: colas, agentes, categorías, políticas y calendarios propios, y tickets que pasan de un área a otra.

---

## Decisión

El usuario eligió la **estrategia A**, después de pedir una explicación más detallada de ella:
- **Infraestructura**:
  - PostgreSQL administrado con respaldos y réplica de lectura, y la API sin estado con 2 o más réplicas detrás de un balanceador;
  - un worker con la misma imagen de la API;
  - las migraciones pasan a ser un paso del despliegue.
- **Áreas**: `Area` como dimensión de primera clase. Las categorías, las políticas de SLA, los feriados y los agentes (`agent_areas`) pertenecen a un área, y el área del ticket se deduce de la categoría. La migración desde el MVP es aditiva: se crea un área inicial a la que se asigna todo lo existente.
- **Autorización** por rol y por área en `identity/authorization.py`, con Row Level Security de PostgreSQL como segunda barrera.
- **Ingreso con SSO (OIDC)**: el perfil y las áreas vienen de los grupos del proveedor de identidad.
- **Listados**: paginación por cursor, con los filtros y el orden de FR-024a como parámetros de la API.
- **Ciclo de vida**: dos acciones nuevas, transferir a otra área y reasignar dentro del área, como actualizaciones condicionales con su evento. Los seis estados no cambian.
- **Worker**: los trabajos se encolan en una tabla de PostgreSQL, dentro de la misma transacción que el cambio que los origina, y se toman con `SKIP LOCKED`. Atiende avisos de SLA, notificaciones y cierre automático.
- **Calendario hábil por área**, con feriados, sobre las mismas funciones puras.
- **Métricas por área**, solo sobre la réplica de lectura o sobre vistas materializadas.

---

## Justificación

- **Ataca el problema real con el menor cambio.** El problema no es la carga, que cabe con holgura en una instancia de PostgreSQL, sino modelar las áreas, y A lo resuelve sin dividir la app.
- **Reutiliza lo que el MVP ya probó**: el dominio puro, las transiciones condicionales sin locks, el contrato OpenAPI y los tests con sus gates.
- **Transferir un ticket entre áreas sigue siendo una transacción local.** En B es coordinación entre celdas, y en C, con eventos, un cambio de área en Tickets obliga a actualizar las vistas de los demás servicios.
- **Opera con un equipo chico**: una base, una imagen y un worker, al menor costo de las tres.
- **No cierra caminos.** Un área con exigencias especiales se puede sacar a una celda (B), y Reporting o las notificaciones pueden ser el primer servicio con eventos (C).

---

## Consecuencias

### ✅ Positivas
- Cada paso del plan se puede entregar por separado, como las fases de este proyecto.
- El contrato crece en forma aditiva (`area_id`, paginación y acciones nuevas), así que la web no se rompe.
- Las métricas no compiten con la cola, porque van a la réplica.

### ⚠️ Trade-offs aceptados
- Las 5 áreas comparten un solo despliegue: un error en una versión afecta a todas. Lo mitigan el CI, el smoke y el despliegue gradual de las réplicas.
- El aislamiento entre áreas es lógico, no físico. Lo mitigan los tests de autorización por endpoint y RLS.
- El techo es de unas 10 veces la meta. Más allá hay que particionar `ticket_events` o separar servicios.

---

## Alternativas Consideradas

| Alternativa | Razón de descarte |
|-------------|-------------------|
| B · Celdas por área | Aislamiento total a unas 5 veces el costo de operación. La transferencia entre áreas parte el historial y las métricas globales dependen de un pipeline de replicación |
| C · Servicios por contexto con eventos | El mayor techo, pero sobredimensiona la meta. Suma broker, outbox, idempotencia y versionado de eventos, y el SLA, hoy transaccional, pasa a ser eventual |

---

## Decisiones Relacionadas
- [ADL-003](ADL-003-sqlite-mvp-postgres-path.md): el SQL portable hace posible el paso a PostgreSQL sin reescribir.
- [ADL-005](ADL-005-simulated-auth-signed-token.md): el ingreso simulado se reemplaza por OIDC; el token y la autorización por rol se conservan.
- [ADL-006](ADL-006-docker-compose-same-origin.md): las migraciones salen del arranque al tener varias réplicas.
- [ADL-008](ADL-008-ticket-lifecycle-six-states.md): los seis estados no cambian; transferir y reasignar son acciones nuevas.
- [ADL-009](ADL-009-sla-business-time.md): el calendario puro pasa a recibir la jornada, la zona y los feriados del área.

---

## Notas para el AI (Memoria Técnica)
- Orden del plan: PostgreSQL y migraciones en el despliegue → OIDC → áreas con su autorización → paginación y filtros en la API → transferencia y reasignación → worker → calendario por área con feriados → métricas en la réplica.
- Todo listado nuevo filtra por las áreas de quien consulta en el servicio, nunca solo en la web.
- Un trabajo del worker se encola en la misma transacción que el cambio que lo origina; nunca después del commit.
- Las consultas agregadas van a la réplica de lectura, nunca al primario.
