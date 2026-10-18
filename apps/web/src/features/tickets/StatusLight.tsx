import { Light, type LightVariant } from '../../ui/Light'
import { STATUS_LABEL } from './labels'
import type { TicketStatus } from './types'

// El rojo nunca es el único portador del significado: toda luz lleva su etiqueta en texto.
const STATUS_LIGHT = {
  open: 'holo',
  in_progress: 'ok',
  on_hold: 'warn',
  resolved: 'ok',
  closed: 'off',
  cancelled: 'off',
} as const satisfies Record<TicketStatus, LightVariant>

export function StatusLight({ status }: { status: TicketStatus }) {
  return <Light variant={STATUS_LIGHT[status]} label={STATUS_LABEL[status]} />
}
