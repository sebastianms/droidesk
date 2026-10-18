# ADL-009: SLA en tiempo hábil con un calendario propio de funciones puras

**Fecha:** 2026-10-16
**Estado:** Activo
**Área:** Backend
**Autor:** Usuario + AI Session

---

## Contexto

El usuario definió que el SLA corre en tiempo hábil: de lunes a viernes, de 09:00 a 18:00, en la zona horaria de la organización. Los plazos son Crítica 4 horas hábiles, Alta 1 día hábil, Media 3 días hábiles y Baja 5 días hábiles, y el plazo se pausa mientras el ticket está En espera ([spec](../specs/001-ticketing-mvp/spec.md#clarifications), FR-020 a FR-023). La jornada y la zona horaria son configurables. `America/Santiago` tiene horario de verano. Los feriados quedan fuera del MVP.

---

## Decisión

Un módulo `sla/` con un `BusinessCalendar(zone, opens, closes, workdays)` construido desde la configuración y dos funciones puras: `add_business_minutes(start_utc, minutes, calendar)` y `business_minutes_between(start_utc, end_utc, calendar)`. Avanzan día por día: arman la ventana hábil de cada fecha en la zona de la organización y operan siempre en UTC.

El ticket guarda su vencimiento (`sla_due_at`) y los minutos hábiles acumulados en espera (`sla_paused_minutes`). El vencimiento se recalcula al crear, al cambiar la prioridad y al retomar. El estado del SLA (en plazo, por vencer, vencido, en pausa, cumplido o incumplido) se deriva al leer, con un reloj inyectable. La política guarda el plazo en la unidad del negocio (`hours` o `days`), así que un día hábil equivale a una jornada, sea cual sea su duración.

---

## Justificación

Las librerías existentes no calzan:
- `businesstimedelta` está abandonada y usa pytz.
- `workalendar` trabaja por días, no por minutos.
- pandas es demasiado pesado para dos funciones.
- `holidays` solo resuelve los feriados, que en el MVP no se usan.

Dos funciones puras sin dependencias son fáciles de leer y de probar en forma exhaustiva, incluidos los cambios de horario. Guardar el vencimiento permite ordenar la cola en la base de datos (FR-024); derivar el estado al leer evita que quede desactualizado.

---

## Consecuencias

### ✅ Positivas
- Sin dependencias nuevas, salvo `tzdata` para tener las mismas reglas de zona en todos los entornos.
- Las mismas dos funciones resuelven vencimiento, pausa, reanudación y umbral "por vencer".
- La cola se ordena por un campo indexado.

### ⚠️ Trade-offs aceptados
- El cálculo es O(días del plazo): trivial para plazos de hasta 5 días hábiles.
- Si cambian la jornada o la zona horaria, los vencimientos ya calculados no se recalculan solos.
- Sin feriados: un feriado entre semana cuenta como hábil (deuda técnica registrada en DECISIONS.md).

---

## Alternativas Consideradas

| Alternativa | Razón de descarte |
|-------------|-------------------|
| businesstimedelta | Sin releases desde 2019; usa pytz |
| workalendar | Calcula días hábiles, no minutos hábiles; mantenimiento bajo |
| pandas (`BusinessHour`) | 12 MB más numpy para dos funciones; su manejo del horario de verano no se verificó |
| Horas corridas con sábado y domingo descontados | Un ticket urgente creado de noche vencería antes de que alguien llegue (descartado por el usuario) |
| Guardar el estado del SLA | Quedaría desactualizado con el paso del tiempo |

---

## Decisiones Relacionadas
- [ADL-002](ADL-002-fastapi-sqlmodel-backend.md): el dominio en funciones puras.
- [ADL-003](ADL-003-sqlite-mvp-postgres-path.md): fechas en UTC.
- [ADL-007](ADL-007-pareto-coverage-gates.md): `sla/` es parte del flujo crítico (≥ 90 %).
- [ADL-008](ADL-008-ticket-lifecycle-six-states.md): En espera pausa el plazo.

---

## Notas para el AI (Memoria Técnica)
- Opera siempre en UTC. No restes datetimes de la misma zona local: en los cambios de horario el resultado es incorrecto.
- Rechaza datetimes sin zona con `ValueError`.
- Una jornada inválida (cierre anterior o igual a la apertura) es un error de configuración al iniciar.
- Tests obligatorios:
  - los ejemplos de la spec y del quickstart;
  - inicio antes, durante y después de la jornada, y en fin de semana;
  - vencimiento exacto al cierre de la jornada;
  - cruce de fin de semana;
  - los cambios de horario de `America/Santiago` (2026-04-04 y 2026-09-05);
  - la propiedad `between(s, add(s, m)) == m`;
  - una espera que empieza con el ticket ya vencido.
- Para agregar feriados, extiende `BusinessCalendar` con un conjunto de fechas (por ejemplo, desde la librería `holidays`), sin cambiar la firma de las funciones.

---

## Extensión 2026-10-18 · Ajuste de prioridad (Fase 8)

- **`PATCH /tickets/{id}` con `{priority}`**: solo agentes (un solicitante recibe 403) y mientras el ticket no esté Resuelto ni final (si no, 409). El vencimiento se recalcula desde la creación con el plazo nuevo más los minutos de espera ya acumulados, y se registra `priority_changed` con los valores anterior y nuevo, en la misma transacción.
- **Idempotente**: pedir la prioridad actual responde 200, sin cambios ni evento.
- **Condicional sobre estado, prioridad y minutos de espera**: si entre la lectura y la escritura alguien deja el ticket en espera y lo retoma, el estado queda igual pero las pausas cambian. Sin esa guarda, el vencimiento se calcularía con minutos desactualizados. Si se pierde la carrera, el 409 dice "El ticket cambió mientras ajustabas su prioridad".
- **Consecuencia de las reglas vigentes**: si se sube la prioridad de un ticket En espera y el nuevo vencimiento cae antes del inicio de la espera, el SLA pasa de "En pausa" a "Vencido", y al retomar esa espera no suma minutos. Es la misma regla de "una espera que empieza con el ticket vencido no corre el vencimiento".
