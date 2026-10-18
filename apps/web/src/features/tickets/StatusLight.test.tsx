import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { StatusLight } from './StatusLight'
import type { TicketStatus } from './types'

describe('StatusLight', () => {
  it.each<[TicketStatus, string]>([
    ['open', 'Abierto'],
    ['in_progress', 'En progreso'],
    ['on_hold', 'En espera'],
    ['resolved', 'Resuelto'],
    ['closed', 'Cerrado'],
    ['cancelled', 'Cancelado'],
  ])('says %s in words, not only in color', (status, label) => {
    render(<StatusLight status={status} />)

    expect(screen.getByText(label)).toBeVisible()
  })
})
