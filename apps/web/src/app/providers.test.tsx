import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Providers } from './providers'

describe('Providers', () => {
  it('starts the app on the login screen for an anonymous visitor', async () => {
    render(<Providers />)

    expect(await screen.findByRole('button', { name: 'Ingresar' })).toBeInTheDocument()
    expect(window.location.pathname).toBe('/login')
  })
})
