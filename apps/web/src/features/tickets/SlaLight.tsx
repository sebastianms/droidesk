import { Light, type LightVariant } from '../../ui/Light'
import { DateTime } from './DateTime'
import { SLA_STATE_LABEL } from './labels'
import styles from './SlaLight.module.css'
import type { Sla, SlaState } from './types'

const SLA_LIGHT = {
  on_track: 'ok',
  at_risk: 'warn',
  breached: 'alert',
  paused: 'off',
  met: 'ok',
  missed: 'alert',
} as const satisfies Record<SlaState, LightVariant>

/** El estado del SLA con su vencimiento; un ticket cancelado no tiene estado de SLA. */
export function SlaLight({ sla }: { sla: Sla }) {
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
