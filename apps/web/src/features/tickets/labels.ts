import type { components } from '../../api/schema'

export const STATUS_LABEL = {
  open: 'Abierto',
  in_progress: 'En progreso',
  on_hold: 'En espera',
  resolved: 'Resuelto',
  closed: 'Cerrado',
  cancelled: 'Cancelado',
} as const

export const PRIORITY_LABEL = {
  critical: 'Crítica',
  high: 'Alta',
  medium: 'Media',
  low: 'Baja',
} as const satisfies Record<components['schemas']['Priority'], string>

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
} as const

export const SLA_STATE_LABEL = {
  on_track: 'En plazo',
  at_risk: 'Por vencer',
  breached: 'Vencido',
  paused: 'En pausa',
  met: 'Cumplido',
  missed: 'Incumplido',
} as const
