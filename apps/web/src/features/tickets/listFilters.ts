import type { Priority, SlaState, TicketSummary } from './types'

// El rango de cada código fija su lugar en las opciones del filtro; el de la prioridad, además, el orden al ordenar.
const PRIORITY_RANK = { critical: 0, high: 1, medium: 2, low: 3 } as const satisfies Record<Priority, number>
const SLA_STATE_RANK = {
  breached: 0,
  at_risk: 1,
  on_track: 2,
  paused: 3,
  met: 4,
  missed: 5,
} as const satisfies Record<SlaState, number>

function keysByRank<K extends string>(rank: Record<K, number>): K[] {
  // `Object.keys` pierde el tipo de las claves; el parámetro asegura que son exactamente las de `K`.
  return (Object.keys(rank) as K[]).toSorted((a, b) => rank[a] - rank[b])
}

export const PRIORITIES = keysByRank(PRIORITY_RANK)
export const SLA_STATES = keysByRank(SLA_STATE_RANK)
export const SORT_KEYS = ['due', 'priority', 'recent'] as const

export type SortKey = (typeof SORT_KEYS)[number]

/** Sin un campo, el listado no filtra por él; sin `sort`, conserva el orden en que lo entrega la API. */
export interface ListFilters {
  priority?: Priority
  sla?: SlaState
  sort?: SortKey
}

export type FilterParam = keyof ListFilters

type Comparator = (a: TicketSummary, b: TicketSummary) => number

const byOldest: Comparator = (a, b) => Date.parse(a.created_at) - Date.parse(b.created_at)

/** Vence primero el más próximo; sin vencimiento (en pausa o cancelado) va al final; a igual vencimiento, el más antiguo. */
const byDue: Comparator = (a, b) => {
  const [aDue, bDue] = [a.sla.due_at, b.sla.due_at]
  if (aDue === bDue) return byOldest(a, b)
  if (aDue === null) return 1
  if (bDue === null) return -1
  return Date.parse(aDue) - Date.parse(bDue) || byOldest(a, b)
}

const byPriority: Comparator = (a, b) => PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority] || byDue(a, b)

const byNewest: Comparator = (a, b) => Date.parse(b.created_at) - Date.parse(a.created_at)

const COMPARATORS = { due: byDue, priority: byPriority, recent: byNewest } as const satisfies Record<
  SortKey,
  Comparator
>

function matches(ticket: TicketSummary, { priority, sla }: ListFilters): boolean {
  return (!priority || ticket.priority === priority) && (!sla || ticket.sla.state === sla)
}

/** Los tickets que cumplen los filtros, en el orden pedido (estable); sin orden, el de entrada. No modifica la lista recibida. */
export function applyListFilters(tickets: readonly TicketSummary[], filters: ListFilters): TicketSummary[] {
  const kept = tickets.filter((ticket) => matches(ticket, filters))
  return filters.sort ? kept.toSorted(COMPARATORS[filters.sort]) : kept
}

/** Hay un filtro que puede dejar tickets afuera; solo ordenar no cambia cuántos se ven. */
export function isFiltering({ priority, sla }: ListFilters): boolean {
  return Boolean(priority || sla)
}

/** Hay algo que "Limpiar filtros" devolvería al estado por defecto: un filtro o un orden elegido. */
export function isCustomized(filters: ListFilters): boolean {
  return isFiltering(filters) || Boolean(filters.sort)
}

/** La opción que es igual a `value`; si `value` no es ninguna, `undefined`. */
export function pick<T extends string>(options: readonly T[], value: string | null): T | undefined {
  return options.find((option) => option === value)
}

/** Lee los filtros de la URL; un valor que no reconoce cuenta como no elegido. */
export function readFilters(params: URLSearchParams): ListFilters {
  return {
    priority: pick(PRIORITIES, params.get('priority')),
    sla: pick(SLA_STATES, params.get('sla')),
    sort: pick(SORT_KEYS, params.get('sort')),
  }
}

/** Los mismos parámetros con `name` en `value`; un valor vacío quita el parámetro. Los demás no cambian. */
export function withParam(params: URLSearchParams, name: string, value: string): URLSearchParams {
  const next = new URLSearchParams(params)
  if (value) next.set(name, value)
  else next.delete(name)
  return next
}

const FILTER_PARAMS = ['priority', 'sla', 'sort'] as const satisfies readonly FilterParam[]

export function withoutFilters(params: URLSearchParams): URLSearchParams {
  const next = new URLSearchParams(params)
  for (const name of FILTER_PARAMS) next.delete(name)
  return next
}
