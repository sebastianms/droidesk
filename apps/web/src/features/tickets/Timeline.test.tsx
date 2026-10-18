import { render, screen, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ticketEvent } from '../../test/fixtures'
import { formatDateTime } from './dates'
import { Timeline } from './Timeline'
import type { TicketEvent } from './types'

const ELENA = { id: 5, name: 'Elena Vidal' }

describe('Timeline', () => {
  it.each<[string, Partial<TicketEvent>, string]>([
    ['creation', { kind: 'created' }, 'Ana Rojas creó el ticket'],
    [
      'assignment',
      { kind: 'assigned', actor: ELENA, from_value: null, to_value: 'Elena Vidal' },
      'Elena Vidal tomó el ticket',
    ],
    [
      'status change',
      { kind: 'status_changed', actor: ELENA, from_value: 'in_progress', to_value: 'on_hold' },
      'Elena Vidal cambió el estado de En progreso a En espera',
    ],
    [
      'priority change',
      { kind: 'priority_changed', actor: ELENA, from_value: 'high', to_value: 'low' },
      'Elena Vidal cambió la prioridad de Alta a Baja',
    ],
    ['comment', { kind: 'commented', from_value: null, to_value: null }, 'Ana Rojas agregó un comentario'],
  ])('tells a %s in Spanish with the author', (_name, event, sentence) => {
    render(<Timeline events={[ticketEvent(event)]} />)

    expect(screen.getByText(sentence)).toBeVisible()
  })

  it('shows an unknown value as the server sent it, so no change is hidden', () => {
    const event = ticketEvent({ kind: 'status_changed', from_value: 'open', to_value: 'archived' })

    render(<Timeline events={[event]} />)

    expect(screen.getByText('Ana Rojas cambió el estado de Abierto a archived')).toBeVisible()
  })

  it('does not print "null" when a change brings no previous value', () => {
    const event = ticketEvent({ kind: 'status_changed', from_value: null, to_value: 'open' })

    render(<Timeline events={[event]} />)

    expect(screen.getByRole('listitem')).not.toHaveTextContent('null')
  })

  it('shows the date and local time of each event as a machine-readable time', () => {
    render(<Timeline events={[ticketEvent({ created_at: '2026-10-19T13:05:00Z' })]} />)

    expect(screen.getByText(formatDateTime('2026-10-19T13:05:00Z'))).toHaveAttribute('datetime', '2026-10-19T13:05:00Z')
  })

  it('lists the events in the order the API gives them', () => {
    const events = [
      ticketEvent({ id: 1, kind: 'created' }),
      ticketEvent({ id: 2, kind: 'assigned', actor: ELENA, to_value: 'Elena Vidal' }),
      ticketEvent({ id: 3, kind: 'status_changed', actor: ELENA, from_value: 'open', to_value: 'in_progress' }),
    ]

    render(<Timeline events={events} />)

    const items = within(screen.getByRole('list')).getAllByRole('listitem')
    const sentences = [
      'Ana Rojas creó el ticket',
      'Elena Vidal tomó el ticket',
      'Elena Vidal cambió el estado de Abierto a En progreso',
    ]
    sentences.forEach((sentence, position) => {
      expect(within(items[position]).getByText(sentence)).toBeVisible()
    })
    expect(items).toHaveLength(sentences.length)
  })

  it('says there is nothing yet instead of showing an empty list', () => {
    render(<Timeline events={[]} />)

    expect(screen.getByText('Sin movimientos todavía.')).toBeVisible()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })

  it('offers no way to edit or delete an event', () => {
    render(<Timeline events={[ticketEvent()]} />)

    expect(screen.queryByRole('button')).not.toBeInTheDocument()
    expect(screen.queryByRole('link')).not.toBeInTheDocument()
  })
})
