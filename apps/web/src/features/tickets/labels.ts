import type { Priority, SlaState, TicketAction, TicketStatus, TicketSummary } from './types'

export const STATUS_LABEL = {
  open: 'Abierto',
  in_progress: 'En progreso',
  on_hold: 'En espera',
  resolved: 'Resuelto',
  closed: 'Cerrado',
  cancelled: 'Cancelado',
} as const satisfies Record<TicketStatus, string>

export const PRIORITY_LABEL = {
  critical: 'Crítica',
  high: 'Alta',
  medium: 'Media',
  low: 'Baja',
} as const satisfies Record<Priority, string>

export const ACTION_LABEL = {
  take: 'Tomar',
  cancel: 'Cancelar',
  hold: 'Dejar en espera',
  resume: 'Retomar',
  resolve: 'Resolver',
  close: 'Confirmar cierre',
  reopen: 'Reabrir',
  comment: 'Comentar',
  change_priority: 'Cambiar prioridad',
} as const satisfies Record<TicketAction, string>

export const SLA_STATE_LABEL = {
  on_track: 'En plazo',
  at_risk: 'Por vencer',
  breached: 'Vencido',
  paused: 'En pausa',
  met: 'Cumplido',
  missed: 'Incumplido',
} as const satisfies Record<SlaState, string>

const UNASSIGNED_LABEL = 'Sin asignar'

/** El agente que tiene el ticket, o "Sin asignar" mientras nadie lo haya tomado. */
export function assigneeName({ assignee }: Pick<TicketSummary, 'assignee'>): string {
  return assignee?.name ?? UNASSIGNED_LABEL
}
