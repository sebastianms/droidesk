import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { renderRoutes } from '../test/helpers'
import { ButtonLink } from './ButtonLink'

describe('ButtonLink', () => {
  it('is a link that navigates inside the app without reloading', async () => {
    const { router } = renderRoutes(
      [
        { path: '/', element: <ButtonLink to="/destino">Ir al destino</ButtonLink> },
        { path: '/destino', element: <p>Llegaste</p> },
      ],
      '/',
    )

    const link = screen.getByRole('link', { name: 'Ir al destino' })
    expect(link).toHaveAttribute('href', '/destino')
    await userEvent.click(link)

    expect(await screen.findByText('Llegaste')).toBeVisible()
    expect(router.state.location.pathname).toBe('/destino')
  })

  it('looks like the button of its variant', () => {
    renderRoutes(
      [
        {
          path: '/',
          element: (
            <>
              <ButtonLink to="/a">Principal</ButtonLink>
              <ButtonLink to="/b" variant="secondary">
                Secundario
              </ButtonLink>
            </>
          ),
        },
      ],
      '/',
    )

    expect(screen.getByRole('link', { name: 'Principal' }).className).toMatch(/primary/)
    expect(screen.getByRole('link', { name: 'Secundario' }).className).toMatch(/secondary/)
  })
})
