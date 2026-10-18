import type { ComponentProps } from 'react'
import { Light } from '../../ui/Light'
import { DateTime } from './DateTime'
import { SLA_STATE_LABEL, STATUS_LABEL } from './labels'
import styles from './StatusLight.module.css'
import type { Sla, SlaState, TicketStatus } from './types'

type LightVariant = ComponentProps<typeof Light>['variant']

// El rojo nunca es el único portador del significado: toda luz lleva su etiqueta en texto.
const STATUS_LIGHT = {
  open: 'holo',
  in_progress: 'ok',
  on_hold: 'warn',
  resolved: 'ok',
  closed: 'off',
  cancelled: 'off',
} as const satisfies Record<TicketStatus, LightVariant>

const SLA_LIGHT = {
  on_track: 'ok',
  at_risk: 'warn',
  breached: 'alert',
  paused: 'off',
  met: 'ok',
  missed: 'alert',
} as const satisfies Record<SlaState, LightVariant>

export function StatusLight({ status }: { status: TicketStatus }) {
  return <Light variant={STATUS_LIGHT[status]} label={STATUS_LABEL[status]} />
}

/** El estado del SLA con su vencimiento; un ticket cancelado no tiene estado de SLA. */
export function SlaInfo({ sla }: { sla: Sla }) {
  if (sla.state === null) return <span className={styles.muted}>No aplica</span>

  return (
    <span className={styles.sla}>
      <Light variant={SLA_LIGHT[sla.state]} label={SLA_STATE_LABEL[sla.state]} />
      {sla.due_at && (
        <span className={styles.due}>
          Vencimiento: <DateTime value={sla.due_at} />
        </span>
      )}
    </span>
  )
}
