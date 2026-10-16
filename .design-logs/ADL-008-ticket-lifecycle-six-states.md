# ADL-008: Ciclo de vida del ticket con seis estados y transiciones por rol

**Fecha:** 2026-10-16
**Estado:** Activo
**Área:** Arquitectura
**Autor:** Usuario + AI Session

---

## Contexto

Los estados del ticket son una definición propia que el enunciado pide justificar. Deben responder "¿quién la tiene?", permitir pedir información sin castigar el SLA (con plazos por prioridad y pausa en espera) y cerrar el ciclo con la voz del solicitante. Las reglas se fijaron en Clarify de la feature 001 ([spec](../specs/001-ticketing-mvp/spec.md#clarifications)).

---

## Decisión

Seis estados: `OPEN` (Abierto), `IN_PROGRESS` (En progreso), `ON_HOLD` (En espera), `RESOLVED` (Resuelto), `CLOSED` (Cerrado) y `CANCELLED` (Cancelado).

| Desde | Hacia | Quién |
|---|---|---|
| `OPEN` | `IN_PROGRESS` | Un agente, al tomarlo |
| `OPEN` | `CANCELLED` | El solicitante, mientras nadie lo tomó |
| `IN_PROGRESS` | `ON_HOLD` | El agente asignado |
| `ON_HOLD` | `IN_PROGRESS` | El agente asignado, o automáticamente cuando comenta el solicitante |
| `IN_PROGRESS` | `RESOLVED` | El agente asignado |
| `RESOLVED` | `CLOSED` | El solicitante |
| `RESOLVED` | `IN_PROGRESS` | El solicitante (reapertura, sin reiniciar el plazo) |

`CLOSED` y `CANCELLED` son finales. La máquina vive en el dominio de la API como una tabla declarativa (desde, hacia, rol), y la API informa en cada ticket las acciones permitidas para quien lo consulta.

---

## Justificación

Cada estado responde a una pregunta del negocio:
- **Abierto**: nadie lo tiene, y se ve.
- **En progreso**: tiene dueño.
- **En espera**: la pelota está del lado del solicitante y el SLA se pausa.
- **Resuelto**: mide el tiempo de resolución sin depender de la confirmación.
- **Cerrado**: el solicitante da conformidad.
- **Cancelado**: retira un pedido que nadie tomó, sin ensuciar la cola ni el cumplimiento del SLA.

Una tabla declarativa en un solo lugar evita reglas dispersas en routers o en la web.

---

## Consecuencias

### ✅ Positivas
- Responsabilidad explícita en cada estado, y un SLA justo con el agente.
- Transiciones fáciles de probar en forma exhaustiva, una por fila de la tabla.
- La web no duplica reglas: solo muestra las acciones permitidas.

### ⚠️ Trade-offs aceptados
- Sin reasignación: si el agente asignado no está, el ticket queda detenido (opcional descartado).
- Un ticket Resuelto sin confirmación queda así indefinidamente: el cierre automático está diferido.
- Los agentes no pueden cerrar ni cancelar: la conformidad es del solicitante.

---

## Alternativas Consideradas

| Alternativa | Razón de descarte |
|-------------|-------------------|
| Cuatro estados, sin En espera | El SLA castigaría al agente por esperas que no controla |
| Estado "Asignado" separado de En progreso | Tomar un ticket ya implica trabajarlo: agrega un paso sin valor |
| Estados Rechazado o Duplicado | El agente los resuelve con un comentario; más estados sin valor en el MVP |
| Cancelación desde cualquier estado no final | Corta trabajo en curso y complica la lectura del cumplimiento |

---

## Decisiones Relacionadas
- [ADL-002](ADL-002-fastapi-sqlmodel-backend.md): la máquina de estados es una función pura del dominio.
- [ADL-004](ADL-004-react-vite-spa.md): la web muestra solo las acciones que informa la API.
- [ADL-007](ADL-007-pareto-coverage-gates.md): las transiciones son parte del flujo crítico (≥ 90 %).

---

## Notas para el AI (Memoria Técnica)
- Define las transiciones en una sola tabla declarativa del dominio; no las repitas con `if` en routers, servicios ni en la web.
- No agregues estados ni transiciones sin actualizar este ADL, la spec (FR-011) y los tests de la tabla.
- Reabrir no reinicia el plazo, y una espera que empieza con el ticket vencido no corre el vencimiento.
- Toda transición, incluida la automática por comentario, escribe su evento en el historial dentro de la misma transacción.
