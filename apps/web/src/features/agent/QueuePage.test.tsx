import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { QueuePage } from './QueuePage'

describe('QueuePage', () => {
  it('tells the agent that the queue is clear when there are no tickets', () => {
    render(<QueuePage />)

    expect(screen.getByRole('heading', { name: 'Cola de tickets' })).toBeInTheDocument()
    expect(screen.getByText('Bip-bup: la cola está despejada')).toBeInTheDocument()
  })
})
