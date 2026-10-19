# Quickstart: validar el Ticketing MVP

**Feature**: `001-ticketing-mvp` · **Spec**: [spec.md](spec.md) · **Contrato**: [contracts/rest-api.md](contracts/rest-api.md)

Escenarios para comprobar a mano, o con el smoke end-to-end, que la feature cumple la spec. Los bordes de tiempo del SLA se prueban con tests automáticos con un reloj controlado, porque esperar horas hábiles reales no es práctico.

## Preparación

```bash
./setup.sh                 # verifica Docker, pide la configuración y levanta todo
open http://localhost:8080 # o el puerto elegido en el setup
```

La ayuda "?" de la pantalla de ingreso lista los usuarios de demo: 4 solicitantes y 3 agentes. Para probar dos perfiles a la vez, usa dos navegadores o una ventana privada. En el modo Demo, la cola ya trae 9 tickets en distintos estados, incluido uno vencido y uno en pausa.

El recorrido de los escenarios 1, 6, 8, 9 y 10 está automatizado en el smoke ([ADL-010](../../.design-logs/ADL-010-playwright-e2e-smoke.md)):

```bash
cd e2e && npm ci && npx playwright install chromium
DROIDESK_BASE_URL=http://localhost:8080 npm test
```

## Escenarios

| # | Escenario | Pasos | Resultado esperado | Cubre |
|---|---|---|---|---|
| 1 | Crear un ticket | Ingresar como solicitante → "Nuevo ticket" → completar título, descripción, categoría y prioridad → enviar | Aparece en "Mis tickets" como Abierto, sin asignar, con su vencimiento | US1, FR-005 a FR-007, FR-019 |
| 2 | Validación | Enviar el formulario con el título vacío | Mensaje en el campo; no se crea nada | US1 |
| 3 | Perfiles separados | Como solicitante, abrir la URL de la cola de agentes | Redirige a "Mis tickets"; la API responde 403 | FR-002, FR-003 |
| 4 | Ticket ajeno | Como solicitante, abrir la URL del ticket de otro solicitante | "No encontrado" (la API responde 404) | FR-004, SC-004 |
| 5 | Cola ordenada | Ingresar como agente → "Cola" | Primero el ticket con el vencimiento más próximo; los En espera al final | US5, FR-024, SC-002 |
| 6 | Tomar | Tomar un ticket Abierto | Pasa a En progreso, asignado a quien lo tomó; el historial suma la asignación y el cambio de estado | US2, FR-009, FR-013 |
| 7 | Toma simultánea | Dos agentes, en dos navegadores, toman el mismo ticket casi a la vez | Uno lo obtiene; el otro ve "Este ticket ya fue tomado" | FR-010, SC-005 |
| 8 | Pedir información | Como agente asignado: comentar → "Dejar en espera" | El SLA muestra "En pausa" para ambos perfiles | US4, FR-021, FR-023 |
| 9 | Respuesta del solicitante | Como solicitante, comentar ese ticket | Vuelve solo a En progreso; el historial registra el cambio a nombre del solicitante | US4, FR-018 |
| 10 | Resolver y cerrar | El agente resuelve; el solicitante confirma | Resuelto → Cerrado; SLA "Cumplido" o "Incumplido"; ya no admite comentarios | US2, FR-011, FR-016, FR-023 |
| 11 | Reabrir | El solicitante reabre un ticket Resuelto | Vuelve a En progreso con el mismo vencimiento | FR-011, edge case de reapertura |
| 12 | Cancelar | El solicitante cancela un ticket Abierto; luego intenta cancelar uno tomado | El primero queda Cancelado y sale de la cola; el segundo no ofrece la acción | FR-011, edge case de cancelación |
| 13 | Ajustar prioridad | El agente cambia un ticket de Crítica a Baja | El vencimiento se recalcula desde la creación; el historial muestra el valor anterior y el nuevo | FR-019, FR-022 |
| 14 | Transición inválida | Por API, como solicitante dueño, pedir `close` sobre un ticket que no está Resuelto; después, pedirlo como agente | El dueño recibe 409 `action_not_allowed` con un mensaje claro; el agente, 403 `forbidden`, porque su perfil no puede cerrar | FR-011, SC-006 |
| 15 | Historial inmutable | Revisar el detalle de un ticket con varios cambios | Historial cronológico con autor, fecha y hora, sin opciones de editar ni borrar | US3, FR-013 a FR-015, SC-003 |
| 16 | Ingreso simulado | Abrir la ayuda "?" del login, elegir `elena.vidal` y escribir cualquier contraseña; después, intentar con un usuario inexistente | Elena entra a la cola como agente; el usuario inexistente recibe un mensaje que remite a la ayuda y no se crea | FR-001, edge case de usuario inexistente |

## Verificación rápida por API

```bash
login() {
  curl -s -X POST localhost:8080/api/v1/auth/login -H 'Content-Type: application/json' \
    -d "{\"username\": \"$1\", \"password\": \"demo\"}" | jq -r .access_token
}
ANA=$(login ana.rojas)
ELENA=$(login elena.vidal)

ID=$(curl -s -X POST localhost:8080/api/v1/tickets -H "Authorization: Bearer $ANA" \
  -H 'Content-Type: application/json' \
  -d '{"title": "No enciende el monitor", "description": "Pantalla negra", "category_id": 1}' | jq .id)

curl -s localhost:8080/api/v1/tickets?view=queue -H "Authorization: Bearer $ELENA" | jq '.[0]'

curl -s -X POST localhost:8080/api/v1/tickets/$ID/transitions \
  -H "Authorization: Bearer $ANA" -H 'Content-Type: application/json' \
  -d '{"action": "close"}'   # esperado: 409 action_not_allowed (el ticket no está Resuelto)
```

## Bordes del SLA (tests automáticos con reloj controlado)

Calendario por defecto: lunes a viernes, de 09:00 a 18:00, en `America/Santiago`.

| Caso | Entrada | Vencimiento esperado |
|---|---|---|
| Alta dentro de la jornada | Creado el lunes a las 10:00 | Martes a las 10:00 |
| Alta fuera de la jornada | Creado el viernes a las 20:00 | Lunes a las 18:00 |
| Crítica que cruza el cierre | Creado el lunes a las 16:00 | Martes a las 11:00 |
| Media que cruza el fin de semana | Creado el jueves a las 12:00 | Martes a las 12:00 |
| Baja | Creado el lunes a las 09:00 | Viernes a las 18:00 (45 horas hábiles) |
| Pausa dentro de plazo | Alta del lunes a las 10:00, en espera de 11:00 a 15:00 | Martes a las 14:00 |
| Espera con el ticket ya vencido | Pasa a En espera después del vencimiento | Sigue `breached`; el vencimiento no se corre |
| Por vencer | Alta con menos de 2 h 15 min hábiles restantes | `at_risk` |
