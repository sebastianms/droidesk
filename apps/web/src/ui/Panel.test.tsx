import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Panel } from './Panel'

describe('Panel', () => {
  it('is a region named after its title', () => {
    render(<Panel title="Ingreso">contenido</Panel>)

    expect(screen.getByRole('region', { name: 'Ingreso' })).toHaveTextContent('contenido')
  })

  it('shows the action next to the title', () => {
    render(
      <Panel title="Ingreso" action={<button type="button">Ayuda</button>}>
        contenido
      </Panel>,
    )

    expect(screen.getByRole('button', { name: 'Ayuda' })).toBeInTheDocument()
  })

  it('has no name and no header without a title', () => {
    render(<Panel>contenido</Panel>)

    expect(screen.queryByRole('heading')).not.toBeInTheDocument()
    expect(screen.queryByRole('region')).not.toBeInTheDocument()
  })
})
