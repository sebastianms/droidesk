import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MyTicketsPage } from './MyTicketsPage'

describe('MyTicketsPage', () => {
  it('invites the requester to create a first ticket when there are none', () => {
    render(<MyTicketsPage />)

    expect(screen.getByRole('heading', { name: 'Mis tickets' })).toBeInTheDocument()
    expect(screen.getByText(/todavía no hay tickets/)).toBeInTheDocument()
  })
})
