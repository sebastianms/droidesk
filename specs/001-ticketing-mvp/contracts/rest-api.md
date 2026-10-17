# REST API Contract: Ticketing MVP

**Feature**: `001-ticketing-mvp` · **Modelo**: [data-model.md](../data-model.md)

Diseño del contrato. El archivo versionado `contracts/openapi.json`, en la raíz del repo, lo genera la API y debe coincidir con este documento ([ADL-001](../../../.design-logs/ADL-001-two-apps-openapi-contract.md)).

## Convenciones

- **Base**: `/api`. El navegador la usa en el mismo origen ([ADL-006](../../../.design-logs/ADL-006-docker-compose-same-origin.md)).
- **Autenticación**: `Authorization: Bearer <access_token>` en todo lo que no sea público.
- **Formato**: JSON en UTF-8; fechas en ISO 8601 con zona (UTC).
- **Errores 401, 403, 404 y 409**: siempre con el mismo cuerpo, en español para mostrarlo tal cual:

  ```json
  { "code": "action_not_allowed", "message": "El ticket ya está resuelto." }
  ```

  La excepción es el 422 de validación, que conserva el formato estándar de FastAPI (`{"detail": [{"loc", "msg", "type"}]}`), documentado y tipado en el OpenAPI sin código extra. La web valida antes de enviar, así que el 422 es solo una red de seguridad.

| `code` | HTTP | Cuándo |
|---|---|---|
| `not_authenticated` | 401 | Falta el token, es inválido o expiró |
| `forbidden` | 403 | El rol no permite la operación |
| `not_found` | 404 | No existe, o es un ticket ajeno para un solicitante (no se revela que existe) |
| `already_taken` | 409 | Otro agente tomó el ticket primero |
| `action_not_allowed` | 409 | La acción no está permitida en el estado actual, o no le corresponde a quien la pide |
| — (formato estándar de FastAPI) | 422 | Campos faltantes, vacíos o demasiado largos |

## Esquemas

| Esquema | Campos |
|---|---|
| `User` | `id`, `name`, `email`, `role` (`requester` o `agent`) |
| `UserRef` | `id`, `name` |
| `LoginRequest` | `user_id` |
| `LoginResponse` | `access_token`, `token_type` (`"bearer"`), `expires_at`, `user: User` |
| `Category` | `id`, `name` |
| `SlaPolicy` | `priority`, `rank`, `label`, `description`, `target_amount`, `target_unit` (`hours` o `days`) |
| `Sla` | `state` (`on_track`, `at_risk`, `breached`, `paused`, `met`, `missed` o `null`), `due_at` (`null` si está en pausa o cancelado) |
| `TicketSummary` | `id`, `title`, `status`, `priority`, `category: Category`, `requester: UserRef`, `assignee: UserRef \| null`, `created_at`, `sla: Sla` |
| `TicketDetail` | `TicketSummary` + `description`, `resolved_at`, `closed_at`, `cancelled_at`, `allowed_actions: TicketAction[]`, `history: Event[]`, `comments: Comment[]` |
| `Event` | `id`, `kind`, `actor: UserRef`, `from_value`, `to_value`, `created_at` |
| `Comment` | `id`, `author: UserRef`, `body`, `created_at` |
| `TicketCreate` | `title` (1 a 120), `description` (1 a 5.000), `category_id`, `priority` (opcional; por defecto `medium`) |
| `TicketUpdate` | `priority` |
| `TransitionRequest` | `action`: `take`, `cancel`, `hold`, `resume`, `resolve`, `close` o `reopen` |
| `CommentCreate` | `body` (1 a 2.000) |

Los largos se validan después de recortar los espacios.

## Endpoints

| Método y ruta | Rol | Entrada | Respuesta | Errores |
|---|---|---|---|---|
| `GET /api/health` | público | — | `200 {"status": "ok"}` | — |
| `GET /api/v1/auth/users` | público | — | `200 User[]` | — |
| `POST /api/v1/auth/login` | público | `LoginRequest` | `200 LoginResponse` | 404, 422 |
| `GET /api/v1/me` | ambos | — | `200 User` | 401 |
| `GET /api/v1/categories` | ambos | — | `200 Category[]` | 401 |
| `GET /api/v1/sla-policies` | ambos | — | `200 SlaPolicy[]`, ordenadas por `rank` | 401 |
| `POST /api/v1/tickets` | solicitante | `TicketCreate` | `201 TicketDetail` | 401, 403, 422 |
| `GET /api/v1/tickets` | ambos | `?view=` (ver abajo) | `200 TicketSummary[]` | 401, 403 |
| `GET /api/v1/tickets/{id}` | ambos | — | `200 TicketDetail` | 401, 404 |
| `PATCH /api/v1/tickets/{id}` | agente | `TicketUpdate` | `200 TicketDetail` | 401, 403, 404, 409, 422 |
| `POST /api/v1/tickets/{id}/transitions` | según la acción | `TransitionRequest` | `200 TicketDetail` | 401, 403, 404, 409, 422 |
| `POST /api/v1/tickets/{id}/comments` | ambos | `CommentCreate` | `201 TicketDetail` | 401, 404, 409, 422 |

### Listado: `GET /api/v1/tickets`

| Rol | `view` | Contenido | Orden |
|---|---|---|---|
| Solicitante | `mine` (por defecto; otro valor responde 403) | Sus tickets, en todos los estados | `created_at` descendente |
| Agente | `queue` (por defecto) | Todos los tickets en estados no finales | Reloj corriendo por `sla_due_at` ascendente, luego los `on_hold`, y a igual criterio por `created_at` |
| Agente | `assigned` | Los no finales asignados a quien consulta | El mismo de `queue` |

Sin paginación en el MVP: el volumen lo permite. Queda como deuda técnica para la escala.

### Ciclo de vida: `POST /api/v1/tickets/{id}/transitions`

Un solo endpoint para todas las acciones de estado, de modo que `allowed_actions` y las transiciones se correspondan 1:1 ([ADL-008](../../../.design-logs/ADL-008-ticket-lifecycle-six-states.md)). La API valida el estado actual, el rol y la relación con el ticket. `take` y `cancel` son actualizaciones condicionales: si otro las ganó antes, responden `already_taken` o `action_not_allowed`.

### Comentarios: `POST /api/v1/tickets/{id}/comments`

Devuelve el `TicketDetail` actualizado, porque un comentario del solicitante sobre un ticket `on_hold` lo pasa a `in_progress` (FR-018).

## Ejemplo

```http
POST /api/v1/tickets/42/transitions
Authorization: Bearer eyJ...
Content-Type: application/json

{ "action": "take" }
```

```json
{
  "id": 42,
  "title": "No puedo entrar a la VPN",
  "status": "in_progress",
  "priority": "high",
  "category": { "id": 4, "name": "Red y conectividad" },
  "requester": { "id": 1, "name": "Ana Rojas" },
  "assignee": { "id": 5, "name": "Elena Vidal" },
  "created_at": "2026-10-19T13:05:00Z",
  "sla": { "state": "on_track", "due_at": "2026-10-20T13:05:00Z" },
  "description": "Desde esta mañana la VPN rechaza mis credenciales.",
  "resolved_at": null,
  "closed_at": null,
  "cancelled_at": null,
  "allowed_actions": ["hold", "resolve", "comment", "change_priority"],
  "history": [
    { "id": 101, "kind": "created", "actor": { "id": 1, "name": "Ana Rojas" }, "from_value": null, "to_value": "open", "created_at": "2026-10-19T13:05:00Z" },
    { "id": 102, "kind": "assigned", "actor": { "id": 5, "name": "Elena Vidal" }, "from_value": null, "to_value": "Elena Vidal", "created_at": "2026-10-19T13:20:00Z" },
    { "id": 103, "kind": "status_changed", "actor": { "id": 5, "name": "Elena Vidal" }, "from_value": "open", "to_value": "in_progress", "created_at": "2026-10-19T13:20:00Z" }
  ],
  "comments": []
}
```
