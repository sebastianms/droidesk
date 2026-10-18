import type { SortKey } from './listFilters'
import type { Priority, SlaPolicy, SlaState, TargetUnit, TicketAction, TicketStatus, TicketSummary } from './types'

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

export const SORT_LABEL = {
  due: 'Vencimiento',
  priority: 'Prioridad',
  recent: 'Más recientes',
} as const satisfies Record<SortKey, string>

const TARGET_UNIT_LABEL = {
  hours: { one: 'hora hábil', many: 'horas hábiles' },
  days: { one: 'día hábil', many: 'días hábiles' },
} as const satisfies Record<TargetUnit, { one: string; many: string }>

/** La prioridad con el plazo que compromete, como "Crítica · 4 horas hábiles". */
export function policyLabel({ label, target_amount, target_unit }: SlaPolicy): string {
  const unit = TARGET_UNIT_LABEL[target_unit]
  return `${label} · ${target_amount} ${target_amount === 1 ? unit.one : unit.many}`
}

const UNASSIGNED_LABEL = 'Sin asignar'

/** El agente que tiene el ticket, o "Sin asignar" mientras nadie lo haya tomado. */
export function assigneeName({ assignee }: Pick<TicketSummary, 'assignee'>): string {
  return assignee?.name ?? UNASSIGNED_LABEL
}

/** "Sin comentarios", "1 comentario" o "N comentarios". */
export function commentCountLabel(count: number): string {
  if (count === 0) return 'Sin comentarios'
  return count === 1 ? '1 comentario' : `${count} comentarios`
}

/** "Mostrando N de M tickets"; el total en singular es "1 ticket". */
export function shownCountLabel(shown: number, total: number): string {
  return `Mostrando ${shown} de ${total} ${total === 1 ? 'ticket' : 'tickets'}`
}
