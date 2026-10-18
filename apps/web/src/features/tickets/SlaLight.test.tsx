import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { formatDateTime } from './dates'
import { SlaLight } from './SlaLight'
import type { SlaState } from './types'

describe('SlaLight', () => {
  it.each<[SlaState, string]>([
    ['on_track', 'En plazo'],
    ['at_risk', 'Por vencer'],
    ['breached', 'Vencido'],
    ['paused', 'En pausa'],
    ['met', 'Cumplido'],
    ['missed', 'Incumplido'],
  ])('says %s in words, not only in color', (state, label) => {
    render(<SlaLight sla={{ state, due_at: null }} />)

    expect(screen.getByText(label)).toBeVisible()
  })

  it('shows the due date when there is one', () => {
    render(<SlaLight sla={{ state: 'at_risk', due_at: '2026-10-20T13:05:00Z' }} />)

    expect(screen.getByText(/Vencimiento:/)).toBeVisible()
    expect(screen.getByText(formatDateTime('2026-10-20T13:05:00Z'))).toHaveAttribute('datetime', '2026-10-20T13:05:00Z')
  })

  it('shows no due date while the clock is paused', () => {
    render(<SlaLight sla={{ state: 'paused', due_at: null }} />)

    expect(screen.queryByText(/Vencimiento:/)).not.toBeInTheDocument()
  })

  it('says the SLA does not apply when the ticket has no SLA state, as a cancelled one', () => {
    render(<SlaLight sla={{ state: null, due_at: null }} />)

    expect(screen.getByText('No aplica')).toBeVisible()
  })
})
