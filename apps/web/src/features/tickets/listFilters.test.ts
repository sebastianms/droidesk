import { describe, expect, it } from 'vitest'
import { ticketSummary } from '../../test/fixtures'
import {
  applyListFilters,
  isCustomized,
  isFiltering,
  type ListFilters,
  PRIORITIES,
  pick,
  readFilters,
  SLA_STATES,
  SORT_KEYS,
  withoutFilters,
  withParam,
} from './listFilters'
import type { Priority, SlaState, TicketSummary } from './types'

function ticket(
  id: number,
  fields: { priority?: Priority; state?: SlaState | null; due?: string | null; created?: string } = {},
): TicketSummary {
  const {
    priority = 'medium',
    state = 'on_track',
    due = '2026-10-20T10:00:00Z',
    created = '2026-10-19T10:00:00Z',
  } = fields
  return ticketSummary({ id, priority, created_at: created, sla: { state, due_at: due } })
}

function ids(tickets: TicketSummary[]): number[] {
  return tickets.map((item) => item.id)
}

function idsAfter(tickets: TicketSummary[], filters: ListFilters): number[] {
  return ids(applyListFilters(tickets, filters))
}

describe('the options', () => {
  it('lists the priorities from the most to the least urgent', () => {
    expect(PRIORITIES).toEqual(['critical', 'high', 'medium', 'low'])
  })

  it('lists the SLA states from the one that needs attention first to the one that needs it last', () => {
    expect(SLA_STATES).toEqual(['breached', 'at_risk', 'on_track', 'paused', 'met', 'missed'])
  })

  it('offers the three ways to sort', () => {
    expect(SORT_KEYS).toEqual(['due', 'priority', 'recent'])
  })
})

describe('applyListFilters', () => {
  describe('without filters or sort', () => {
    it('keeps every ticket in the order the API gave them', () => {
      const tickets = [ticket(3, { priority: 'low' }), ticket(1, { priority: 'critical' }), ticket(2)]

      expect(idsAfter(tickets, {})).toEqual([3, 1, 2])
    })

    it('returns a new list and leaves the received one untouched', () => {
      const tickets = [ticket(2, { created: '2026-10-19T10:00:00Z' }), ticket(1, { created: '2026-10-19T11:00:00Z' })]

      const result = applyListFilters(tickets, { sort: 'recent' })

      expect(result).not.toBe(tickets)
      expect(ids(tickets)).toEqual([2, 1])
    })
  })

  describe('filtering by priority', () => {
    const tickets = [
      ticket(1, { priority: 'low' }),
      ticket(2, { priority: 'critical' }),
      ticket(3, { priority: 'low' }),
      ticket(4, { priority: 'high' }),
    ]

    it.each<[Priority, number[]]>([
      ['critical', [2]],
      ['high', [4]],
      ['medium', []],
      ['low', [1, 3]],
    ])('keeps only the %s tickets, in their order', (priority, expected) => {
      expect(idsAfter(tickets, { priority })).toEqual(expected)
    })
  })

  describe('filtering by SLA state', () => {
    const tickets = [
      ticket(1, { state: 'breached' }),
      ticket(2, { state: 'at_risk' }),
      ticket(3, { state: 'on_track' }),
      ticket(4, { state: 'paused', due: null }),
      ticket(5, { state: 'met' }),
      ticket(6, { state: 'missed' }),
      ticket(7, { state: null, due: null }),
    ]

    it.each<[SlaState, number[]]>([
      ['breached', [1]],
      ['at_risk', [2]],
      ['on_track', [3]],
      ['paused', [4]],
      ['met', [5]],
      ['missed', [6]],
    ])('keeps only the %s tickets', (sla, expected) => {
      expect(idsAfter(tickets, { sla })).toEqual(expected)
    })

    it('shows a cancelled ticket, which has no SLA state, only when the SLA is not filtered', () => {
      expect(idsAfter(tickets, {})).toContain(7)
      for (const sla of SLA_STATES) expect(idsAfter(tickets, { sla })).not.toContain(7)
    })
  })

  it('keeps only the tickets that match the priority and the SLA state together', () => {
    const tickets = [
      ticket(1, { priority: 'critical', state: 'breached' }),
      ticket(2, { priority: 'critical', state: 'on_track' }),
      ticket(3, { priority: 'low', state: 'breached' }),
    ]

    expect(idsAfter(tickets, { priority: 'critical', sla: 'breached' })).toEqual([1])
  })

  it('returns nothing when no ticket matches', () => {
    expect(idsAfter([ticket(1, { priority: 'low' })], { priority: 'critical' })).toEqual([])
  })

  describe('sorting by due date', () => {
    it('puts the nearest due date first', () => {
      const tickets = [
        ticket(1, { due: '2026-10-22T10:00:00Z' }),
        ticket(2, { due: '2026-10-20T10:00:00Z' }),
        ticket(3, { due: '2026-10-21T10:00:00Z' }),
      ]

      expect(idsAfter(tickets, { sort: 'due' })).toEqual([2, 3, 1])
    })

    it.each([
      ['before', [ticket(1, { state: 'paused', due: null }), ticket(2)]],
      ['after', [ticket(2), ticket(1, { state: 'paused', due: null })]],
    ])('puts a ticket with no due date last when it comes %s one that has it', (_position, tickets) => {
      expect(idsAfter(tickets, { sort: 'due' })).toEqual([2, 1])
    })

    it('puts the tickets with no due date last, whatever their status', () => {
      const tickets = [
        ticket(1, { state: 'paused', due: null }),
        ticket(2, { due: '2026-10-25T10:00:00Z' }),
        ticket(3, { state: null, due: null }),
        ticket(4, { due: '2026-10-21T10:00:00Z' }),
      ]

      expect(idsAfter(tickets, { sort: 'due' })).toEqual([4, 2, 1, 3])
    })

    it('breaks a tie by the oldest creation date, with or without a due date', () => {
      const tickets = [
        ticket(1, { due: '2026-10-21T10:00:00Z', created: '2026-10-19T12:00:00Z' }),
        ticket(2, { due: '2026-10-21T10:00:00Z', created: '2026-10-19T09:00:00Z' }),
        ticket(3, { state: 'paused', due: null, created: '2026-10-19T11:00:00Z' }),
        ticket(4, { state: 'paused', due: null, created: '2026-10-19T08:00:00Z' }),
      ]

      expect(idsAfter(tickets, { sort: 'due' })).toEqual([2, 1, 4, 3])
    })

    it('breaks a tie between the same instant written with different offsets by the oldest creation date', () => {
      const tickets = [
        ticket(1, { due: '2026-10-20T10:00:00+02:00', created: '2026-10-19T12:00:00Z' }),
        ticket(2, { due: '2026-10-20T08:00:00Z', created: '2026-10-19T09:00:00Z' }),
      ]

      expect(idsAfter(tickets, { sort: 'due' })).toEqual([2, 1])
    })

    it('compares instants, not text, so a different UTC offset does not fool it', () => {
      const tickets = [
        ticket(1, { due: '2026-10-20T09:00:00Z' }),
        ticket(2, { due: '2026-10-20T10:00:00+02:00' }),
        ticket(3, { due: '2026-10-20T08:30:00Z' }),
      ]

      expect(idsAfter(tickets, { sort: 'due' })).toEqual([2, 3, 1])
    })
  })

  describe('sorting by priority', () => {
    it('goes from critical to low', () => {
      const tickets = [
        ticket(1, { priority: 'low' }),
        ticket(2, { priority: 'critical' }),
        ticket(3, { priority: 'medium' }),
        ticket(4, { priority: 'high' }),
      ]

      expect(idsAfter(tickets, { sort: 'priority' })).toEqual([2, 4, 3, 1])
    })

    it('orders the tickets of the same priority by due date, the ones with none last', () => {
      const tickets = [
        ticket(1, { priority: 'high', state: 'paused', due: null }),
        ticket(2, { priority: 'high', due: '2026-10-22T10:00:00Z' }),
        ticket(3, { priority: 'critical', due: '2026-10-30T10:00:00Z' }),
        ticket(4, { priority: 'high', due: '2026-10-21T10:00:00Z' }),
      ]

      expect(idsAfter(tickets, { sort: 'priority' })).toEqual([3, 4, 2, 1])
    })
  })

  describe('sorting by most recent', () => {
    it('puts the latest creation date first', () => {
      const tickets = [
        ticket(1, { created: '2026-10-19T09:00:00Z' }),
        ticket(2, { created: '2026-10-19T11:00:00Z' }),
        ticket(3, { created: '2026-10-19T10:00:00Z' }),
      ]

      expect(idsAfter(tickets, { sort: 'recent' })).toEqual([2, 3, 1])
    })

    it('is stable: tickets created at the same moment keep the order they came in', () => {
      const tickets = [ticket(5), ticket(2), ticket(9)]

      expect(idsAfter(tickets, { sort: 'recent' })).toEqual([5, 2, 9])
    })
  })

  it('filters first and sorts what is left', () => {
    const tickets = [
      ticket(1, { priority: 'low', state: 'at_risk', due: '2026-10-23T10:00:00Z' }),
      ticket(2, { priority: 'critical', state: 'on_track', due: '2026-10-20T10:00:00Z' }),
      ticket(3, { priority: 'high', state: 'at_risk', due: '2026-10-21T10:00:00Z' }),
      ticket(4, { priority: 'critical', state: 'at_risk', due: '2026-10-22T10:00:00Z' }),
    ]

    expect(idsAfter(tickets, { sla: 'at_risk', sort: 'priority' })).toEqual([4, 3, 1])
    expect(idsAfter(tickets, { sla: 'at_risk', sort: 'due' })).toEqual([3, 4, 1])
  })
})

describe('isFiltering and isCustomized', () => {
  it.each<[string, ListFilters, boolean, boolean]>([
    ['nothing chosen', {}, false, false],
    ['a priority', { priority: 'low' }, true, true],
    ['an SLA state', { sla: 'met' }, true, true],
    ['only a sort order', { sort: 'due' }, false, true],
    ['everything', { priority: 'low', sla: 'met', sort: 'recent' }, true, true],
  ])('with %s', (_name, filters, filtering, customized) => {
    expect(isFiltering(filters)).toBe(filtering)
    expect(isCustomized(filters)).toBe(customized)
  })
})

describe('pick', () => {
  it('gives the option that equals the value', () => {
    expect(pick(PRIORITIES, 'high')).toBe('high')
  })

  it.each([['urgent'], ['High'], [''], [null]])('gives nothing for %j, which is not an option', (value) => {
    expect(pick(PRIORITIES, value)).toBeUndefined()
  })
})

describe('readFilters', () => {
  it('reads the priority, the SLA state and the sort order from the address', () => {
    expect(readFilters(new URLSearchParams('priority=critical&sla=at_risk&sort=priority'))).toEqual({
      priority: 'critical',
      sla: 'at_risk',
      sort: 'priority',
    })
  })

  it('reads nothing when the address has none of them', () => {
    expect(readFilters(new URLSearchParams('view=assigned'))).toEqual({})
  })

  it('ignores the values it does not know and keeps the ones it does', () => {
    const params = new URLSearchParams('priority=urgent&sla=Breached&sort=oldest&view=assigned')

    expect(readFilters(params)).toEqual({})
    expect(readFilters(new URLSearchParams('priority=urgent&sla=met'))).toEqual({ sla: 'met' })
  })

  it('ignores empty values and values with the wrong case', () => {
    expect(readFilters(new URLSearchParams('priority=&sla=&sort=DUE'))).toEqual({})
    expect(readFilters(new URLSearchParams('priority=Critical'))).toEqual({})
  })
})

describe('withParam', () => {
  it('adds a parameter and keeps the others', () => {
    const next = withParam(new URLSearchParams('view=assigned'), 'priority', 'critical')

    expect(next.toString()).toBe('view=assigned&priority=critical')
  })

  it('sets a parameter that is not a filter, like the view, and keeps the filters', () => {
    const next = withParam(new URLSearchParams('priority=low&sort=due'), 'view', 'assigned')

    expect(next.toString()).toBe('priority=low&sort=due&view=assigned')
  })

  it('replaces the value a parameter already had', () => {
    const next = withParam(new URLSearchParams('priority=low&sla=met'), 'priority', 'high')

    expect(next.toString()).toBe('priority=high&sla=met')
  })

  it('removes the parameter when the value is empty', () => {
    const next = withParam(new URLSearchParams('view=queue&sla=met'), 'sla', '')

    expect(next.toString()).toBe('view=queue')
  })

  it('does not change the parameters it receives', () => {
    const params = new URLSearchParams('priority=low')

    withParam(params, 'priority', 'high')

    expect(params.toString()).toBe('priority=low')
  })
})

describe('withoutFilters', () => {
  it('removes the priority, the SLA state and the sort order, and keeps the rest', () => {
    const params = new URLSearchParams('view=assigned&priority=low&sla=met&sort=due')

    expect(withoutFilters(params).toString()).toBe('view=assigned')
    expect(params.toString()).toBe('view=assigned&priority=low&sla=met&sort=due')
  })
})
