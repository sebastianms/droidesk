import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { IconButton } from './IconButton'

describe('IconButton', () => {
  it('is named by its label, not by its glyph', () => {
    render(<IconButton label="Ver usuarios de demo">?</IconButton>)

    expect(screen.getByRole('button', { name: 'Ver usuarios de demo' })).toBeInTheDocument()
  })

  it('hides the glyph from assistive technology', () => {
    render(<IconButton label="Ver usuarios de demo">?</IconButton>)

    expect(screen.getByText('?')).toHaveAttribute('aria-hidden', 'true')
  })

  it('does not submit a form unless it is told to', () => {
    render(<IconButton label="Ayuda">?</IconButton>)

    expect(screen.getByRole('button', { name: 'Ayuda' })).toHaveAttribute('type', 'button')
  })

  it('passes the state attributes through', () => {
    render(
      <IconButton label="Ayuda" aria-expanded={true} aria-controls="panel">
        ?
      </IconButton>,
    )

    const button = screen.getByRole('button', { name: 'Ayuda' })
    expect(button).toHaveAttribute('aria-expanded', 'true')
    expect(button).toHaveAttribute('aria-controls', 'panel')
  })

  it('reports clicks', async () => {
    const onClick = vi.fn()
    render(
      <IconButton label="Ayuda" onClick={onClick}>
        ?
      </IconButton>,
    )

    await userEvent.click(screen.getByRole('button', { name: 'Ayuda' }))

    expect(onClick).toHaveBeenCalledOnce()
  })
})
