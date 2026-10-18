import { DateTime } from './DateTime'
import { PRIORITY_LABEL, STATUS_LABEL } from './labels'
import styles from './Timeline.module.css'
import type { EventKind, TicketEvent } from './types'

/** Los códigos que el servidor agregue y esta pantalla no conozca se muestran tal cual, para no ocultar un cambio. */
function labelOf(labels: Readonly<Record<string, string>>, code: string | null): string {
  return code === null ? '' : (labels[code] ?? code)
}

// Lo que cada tipo de evento dice del autor, tal como se lee después de su nombre.
const EVENT_TEXT = {
  created: () => 'creó el ticket',
  assigned: () => 'tomó el ticket',
  status_changed: ({ from_value, to_value }) =>
    `cambió el estado de ${labelOf(STATUS_LABEL, from_value)} a ${labelOf(STATUS_LABEL, to_value)}`,
  priority_changed: ({ from_value, to_value }) =>
    `cambió la prioridad de ${labelOf(PRIORITY_LABEL, from_value)} a ${labelOf(PRIORITY_LABEL, to_value)}`,
  commented: () => 'agregó un comentario',
} satisfies Record<EventKind, (event: TicketEvent) => string>

/** El historial del ticket, de solo lectura y del más antiguo al más reciente, como lo entrega la API. */
export function Timeline({ events }: { events: TicketEvent[] }) {
  if (events.length === 0) return <p>Sin movimientos todavía.</p>

  return (
    <ol className={styles.timeline}>
      {events.map((event) => (
        <li key={event.id} className={styles.event}>
          <p className={styles.text}>{`${event.actor.name} ${EVENT_TEXT[event.kind](event)}`}</p>
          <span className={styles.when}>
            <DateTime value={event.created_at} />
          </span>
        </li>
      ))}
    </ol>
  )
}
