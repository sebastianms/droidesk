import type { Category, SlaPolicy, TicketDetail, TicketEvent, TicketSummary } from '../features/tickets/types'

export const categories: Category[] = [
  { id: 1, name: 'Hardware' },
  { id: 2, name: 'Software' },
  { id: 3, name: 'Accesos y cuentas' },
  { id: 4, name: 'Red y conectividad' },
]

export const slaPolicies: SlaPolicy[] = [
  {
    priority: 'critical',
    rank: 1,
    label: 'Crítica',
    description: 'Servicio caído o bloqueo total. Plazo: 4 horas hábiles.',
    target_amount: 4,
    target_unit: 'hours',
  },
  {
    priority: 'high',
    rank: 2,
    label: 'Alta',
    description: 'Una persona no puede trabajar. Plazo: 1 día hábil.',
    target_amount: 1,
    target_unit: 'days',
  },
  {
    priority: 'medium',
    rank: 3,
    label: 'Media',
    description: 'Algo falla, pero se puede seguir trabajando. Plazo: 3 días hábiles.',
    target_amount: 3,
    target_unit: 'days',
  },
  {
    priority: 'low',
    rank: 4,
    label: 'Baja',
    description: 'Consulta o mejora sin urgencia. Plazo: 5 días hábiles.',
    target_amount: 5,
    target_unit: 'days',
  },
]

export function ticketSummary(overrides: Partial<TicketSummary> = {}): TicketSummary {
  return {
    id: 42,
    title: 'No puedo entrar a la VPN',
    status: 'open',
    priority: 'high',
    category: { id: 4, name: 'Red y conectividad' },
    requester: { id: 1, name: 'Ana Rojas' },
    assignee: null,
    created_at: '2026-10-19T13:05:00Z',
    sla: { state: 'on_track', due_at: '2026-10-20T13:05:00Z' },
    ...overrides,
  }
}

export function ticketDetail(overrides: Partial<TicketDetail> = {}): TicketDetail {
  return {
    ...ticketSummary(),
    description: 'Desde esta mañana la VPN rechaza mis credenciales.',
    resolved_at: null,
    closed_at: null,
    cancelled_at: null,
    allowed_actions: ['cancel', 'comment'],
    history: [],
    ...overrides,
  }
}

export function ticketEvent(overrides: Partial<TicketEvent> = {}): TicketEvent {
  return {
    id: 1,
    kind: 'created',
    actor: { id: 1, name: 'Ana Rojas' },
    from_value: null,
    to_value: 'open',
    created_at: '2026-10-19T13:05:00Z',
    ...overrides,
  }
}
