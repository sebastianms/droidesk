import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { agentElena, demoUsers, jsonResponse, renderRoutes, requesterAna, stubApi } from '../../test/helpers'
import { USERNAME_RULE } from './credentials'
import { LoginPage } from './LoginPage'
import { getSession } from './session'

const LOGIN = 'POST /api/v1/auth/login'
const USERS = 'GET /api/v1/auth/users'
const UNKNOWN_USER = 'El usuario no existe. Revisa los usuarios de demo en el ícono ?.'

function loginResponse(user: typeof agentElena) {
  return { access_token: `token-${user.id}`, token_type: 'bearer', expires_at: '2999-01-01T00:00:00Z', user }
}

function renderLogin() {
  return renderRoutes(
    [
      { path: '/login', element: <LoginPage /> },
      { path: '/requester', element: <p>Vista del solicitante</p> },
      { path: '/agent', element: <p>Vista del agente</p> },
    ],
    '/login',
  )
}

async function fillIn(username: string, password: string) {
  if (username) await userEvent.type(screen.getByLabelText('Usuario'), username)
  if (password) await userEvent.type(screen.getByLabelText('Contraseña'), password)
}

async function submit() {
  await userEvent.click(screen.getByRole('button', { name: 'Ingresar' }))
}

async function openDemoUsers() {
  await userEvent.click(screen.getByRole('button', { name: 'Ver usuarios de demo' }))
}

async function sentBody(fetchMock: ReturnType<typeof stubApi>) {
  const request = fetchMock.mock.calls.map(([sent]) => sent).find((sent) => sent.method === 'POST')
  return request?.json()
}

describe('LoginPage', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('form', () => {
    it('asks for a username and a password', () => {
      stubApi({})

      renderLogin()

      expect(screen.getByLabelText('Usuario')).toHaveAttribute('autocomplete', 'username')
      expect(screen.getByLabelText('Contraseña')).toHaveAttribute('type', 'password')
      expect(screen.getByLabelText('Contraseña')).toHaveAttribute('autocomplete', 'current-password')
      expect(screen.getByRole('button', { name: 'Ingresar' })).toBeEnabled()
    })

    it('does not ask for a profile: the user already has one', () => {
      stubApi({})

      renderLogin()

      expect(screen.queryByRole('radio')).not.toBeInTheDocument()
      expect(screen.queryByRole('group', { name: 'Perfil' })).not.toBeInTheDocument()
    })

    it('explains that the login is simulated and points to the demo users', () => {
      stubApi({})

      renderLogin()

      expect(
        screen.getByText('Ingreso simulado: usa uno de los usuarios de demo; cualquier contraseña sirve.'),
      ).toBeVisible()
    })

    it('does not call the API until the demo users are opened or the form is sent', () => {
      const fetchMock = stubApi({})

      renderLogin()

      expect(fetchMock).not.toHaveBeenCalled()
    })
  })

  describe('demo users help', () => {
    it('has an accessible question mark button that starts collapsed', () => {
      stubApi({})

      renderLogin()

      const button = screen.getByRole('button', { name: 'Ver usuarios de demo' })
      expect(button).toHaveAttribute('aria-expanded', 'false')
      expect(document.getElementById(button.getAttribute('aria-controls') ?? '')).not.toBeVisible()
    })

    it('opens a panel with the demo users grouped by profile', async () => {
      stubApi({ [USERS]: () => jsonResponse(demoUsers) })
      renderLogin()

      await openDemoUsers()

      expect(screen.getByRole('button', { name: 'Ver usuarios de demo' })).toHaveAttribute('aria-expanded', 'true')
      expect(await screen.findByRole('region', { name: 'Solicitantes' })).toBeVisible()
      expect(screen.getByRole('region', { name: 'Agentes' })).toBeVisible()
    })

    it('closes the panel with a second click on the button', async () => {
      stubApi({ [USERS]: () => jsonResponse(demoUsers) })
      renderLogin()
      await openDemoUsers()
      await screen.findByRole('region', { name: 'Agentes' })

      await openDemoUsers()

      expect(screen.getByRole('button', { name: 'Ver usuarios de demo' })).toHaveAttribute('aria-expanded', 'false')
      expect(screen.queryByRole('region', { name: 'Agentes' })).not.toBeInTheDocument()
    })

    it('fills in the username, closes the panel and moves the focus to the password', async () => {
      stubApi({ [USERS]: () => jsonResponse(demoUsers) })
      renderLogin()
      await openDemoUsers()

      await userEvent.click(await screen.findByRole('button', { name: /Elena Vidal/ }))

      expect(screen.getByLabelText('Usuario')).toHaveValue('elena.vidal')
      expect(screen.getByRole('button', { name: 'Ver usuarios de demo' })).toHaveAttribute('aria-expanded', 'false')
      expect(screen.getByLabelText('Contraseña')).toHaveFocus()
    })

    it('replaces what was already typed in the username', async () => {
      stubApi({ [USERS]: () => jsonResponse(demoUsers) })
      renderLogin()
      await fillIn('otra.persona', '')
      await openDemoUsers()

      await userEvent.click(await screen.findByRole('button', { name: /Ana Rojas/ }))

      expect(screen.getByLabelText('Usuario')).toHaveValue('ana.rojas')
    })

    it('clears the complaint about an empty username when one is picked', async () => {
      stubApi({ [USERS]: () => jsonResponse(demoUsers) })
      renderLogin()
      await submit()
      await openDemoUsers()

      await userEvent.click(await screen.findByRole('button', { name: /Ana Rojas/ }))

      expect(screen.getByLabelText('Usuario')).not.toHaveAttribute('aria-invalid')
    })

    it('closes with Escape without stealing the focus from a form field', async () => {
      stubApi({ [USERS]: () => jsonResponse(demoUsers) })
      renderLogin()
      await openDemoUsers()
      screen.getByLabelText('Contraseña').focus()

      await userEvent.keyboard('{Escape}')

      expect(screen.getByRole('button', { name: 'Ver usuarios de demo' })).toHaveAttribute('aria-expanded', 'false')
      expect(screen.getByLabelText('Contraseña')).toHaveFocus()
    })

    it('closes with Escape while the focus is on the button and keeps it there', async () => {
      stubApi({ [USERS]: () => jsonResponse(demoUsers) })
      renderLogin()
      await openDemoUsers()

      await userEvent.keyboard('{Escape}')

      const button = screen.getByRole('button', { name: 'Ver usuarios de demo' })
      expect(button).toHaveAttribute('aria-expanded', 'false')
      expect(button).toHaveFocus()
    })

    it('closes with Escape while the focus is inside the panel and gives the focus back to the button', async () => {
      stubApi({ [USERS]: () => jsonResponse(demoUsers) })
      renderLogin()
      await openDemoUsers()
      const user = await screen.findByRole('button', { name: /Bruno Castillo/ })
      user.focus()

      await userEvent.keyboard('{Escape}')

      expect(screen.getByRole('button', { name: 'Ver usuarios de demo' })).toHaveFocus()
      expect(screen.queryByRole('region', { name: 'Solicitantes' })).not.toBeInTheDocument()
    })

    it('does not touch the focus when Escape is pressed with the panel closed', async () => {
      stubApi({})
      renderLogin()
      screen.getByLabelText('Usuario').focus()

      await userEvent.keyboard('{Escape}')

      expect(screen.getByLabelText('Usuario')).toHaveFocus()
    })

    it('signs in with the user that was picked', async () => {
      const fetchMock = stubApi({
        [USERS]: () => jsonResponse(demoUsers),
        [LOGIN]: () => jsonResponse(loginResponse(agentElena)),
      })
      renderLogin()
      await openDemoUsers()
      await userEvent.click(await screen.findByRole('button', { name: /Elena Vidal/ }))
      await userEvent.keyboard('cualquiera{Enter}')

      expect(await screen.findByText('Vista del agente')).toBeInTheDocument()
      expect(await sentBody(fetchMock)).toEqual({ username: 'elena.vidal', password: 'cualquiera' })
    })
  })

  describe('validation', () => {
    it('asks for both fields and does not call the API when the form is empty', async () => {
      const fetchMock = stubApi({})
      renderLogin()

      await submit()

      expect(screen.getByLabelText('Usuario')).toHaveAccessibleDescription('Escribe tu usuario.')
      expect(screen.getByLabelText('Contraseña')).toHaveAccessibleDescription('Escribe tu contraseña.')
      expect(fetchMock).not.toHaveBeenCalled()
    })

    it('sends the focus to the username when it is the first problem', async () => {
      stubApi({})
      renderLogin()

      await submit()

      expect(screen.getByLabelText('Usuario')).toHaveFocus()
    })

    it('sends the focus to the password when only the password is missing', async () => {
      stubApi({})
      renderLogin()
      await fillIn('ana.rojas', '')

      await submit()

      expect(screen.getByLabelText('Contraseña')).toHaveFocus()
    })

    it('explains the username rule when it has forbidden characters', async () => {
      const fetchMock = stubApi({})
      renderLogin()
      await fillIn('ana rojas', 'cualquiera')

      await submit()

      expect(screen.getByLabelText('Usuario')).toHaveAccessibleDescription(USERNAME_RULE)
      expect(fetchMock).not.toHaveBeenCalled()
    })

    it('stops complaining about a field as soon as the user types in it', async () => {
      stubApi({})
      renderLogin()
      await submit()

      await userEvent.type(screen.getByLabelText('Usuario'), 'a')

      expect(screen.getByLabelText('Usuario')).not.toHaveAttribute('aria-invalid')
      expect(screen.getByLabelText('Contraseña')).toHaveAttribute('aria-invalid', 'true')
    })

    it('describes the field with its error before the focus reaches it, so screen readers announce it', async () => {
      stubApi({})
      renderLogin()
      const describedAtFocus: (string | null)[] = []
      const nativeFocus = HTMLElement.prototype.focus
      vi.spyOn(HTMLElement.prototype, 'focus').mockImplementation(function (this: HTMLElement, options) {
        if (this instanceof HTMLInputElement) describedAtFocus.push(this.getAttribute('aria-describedby'))
        nativeFocus.call(this, options)
      })

      await submit()

      expect(describedAtFocus).toHaveLength(1)
      expect(describedAtFocus[0]).toBe(screen.getByLabelText('Usuario').getAttribute('aria-describedby'))
      expect(describedAtFocus[0]).not.toBeNull()
    })

    it('limits the length of the password to what the API accepts', () => {
      stubApi({})

      renderLogin()

      expect(screen.getByLabelText('Contraseña')).toHaveAttribute('maxlength', '128')
    })
  })

  describe('signing in', () => {
    it('sends only the normalized username and the password', async () => {
      const fetchMock = stubApi({ [LOGIN]: () => jsonResponse(loginResponse(requesterAna)) })
      renderLogin()
      await fillIn('  Ana.Rojas ', 'cualquiera')

      await submit()

      await screen.findByText('Vista del solicitante')
      expect(await sentBody(fetchMock)).toEqual({ username: 'ana.rojas', password: 'cualquiera' })
    })

    it('sends the form with the Enter key', async () => {
      stubApi({ [LOGIN]: () => jsonResponse(loginResponse(requesterAna)) })
      renderLogin()
      await fillIn('ana.rojas', '')

      await userEvent.type(screen.getByLabelText('Contraseña'), 'cualquiera{Enter}')

      expect(await screen.findByText('Vista del solicitante')).toBeInTheDocument()
    })

    it('saves the session and sends a requester to their tickets', async () => {
      stubApi({ [LOGIN]: () => jsonResponse(loginResponse(requesterAna)) })
      renderLogin()
      await fillIn('ana.rojas', 'cualquiera')

      await submit()

      expect(await screen.findByText('Vista del solicitante')).toBeInTheDocument()
      expect(getSession()?.user).toEqual(requesterAna)
    })

    it('sends an agent to the queue', async () => {
      stubApi({ [LOGIN]: () => jsonResponse(loginResponse(agentElena)) })
      renderLogin()
      await fillIn('elena.vidal', 'cualquiera')

      await submit()

      expect(await screen.findByText('Vista del agente')).toBeInTheDocument()
      expect(getSession()?.token).toBe('token-5')
    })

    it('drops cached data from a previous session when someone signs in', async () => {
      stubApi({ [LOGIN]: () => jsonResponse(loginResponse(requesterAna)) })
      const { queryClient } = renderLogin()
      queryClient.setQueryData(['get', '/api/v1/tickets'], [{ id: 1, title: 'Ticket de otra persona' }])
      await fillIn('ana.rojas', 'cualquiera')

      await submit()

      await screen.findByText('Vista del solicitante')
      expect(queryClient.getQueryData(['get', '/api/v1/tickets'])).toBeUndefined()
    })

    it('disables the button while the request is in flight', async () => {
      let answer: (response: Response) => void = () => {}
      const pending = new Promise<Response>((resolve) => {
        answer = resolve
      })
      stubApi({ [LOGIN]: () => pending })
      renderLogin()
      await fillIn('ana.rojas', 'cualquiera')

      await submit()

      expect(await screen.findByRole('button', { name: 'Ingresando...' })).toBeDisabled()
      answer(jsonResponse(loginResponse(requesterAna)))
      expect(await screen.findByText('Vista del solicitante')).toBeInTheDocument()
    })
  })

  describe('failures', () => {
    it('shows the message of the server when the user does not exist, without reloading the page', async () => {
      const assign = vi.fn()
      vi.stubGlobal('location', { origin: window.location.origin, pathname: '/login', assign })
      stubApi({ [LOGIN]: () => jsonResponse({ code: 'not_authenticated', message: UNKNOWN_USER }, 401) })
      renderLogin()
      await fillIn('desconocido', 'cualquiera')

      await submit()

      expect(await screen.findByRole('alert')).toHaveTextContent(UNKNOWN_USER)
      expect(assign).not.toHaveBeenCalled()
      expect(getSession()).toBeNull()
    })

    it('lets the user try again after the user does not exist', async () => {
      const assign = vi.fn()
      vi.stubGlobal('location', { origin: window.location.origin, pathname: '/login', assign })
      let attempts = 0
      stubApi({
        [LOGIN]: () =>
          ++attempts === 1
            ? jsonResponse({ code: 'not_authenticated', message: UNKNOWN_USER }, 401)
            : jsonResponse(loginResponse(requesterAna)),
      })
      renderLogin()
      await fillIn('desconocido', 'cualquiera')
      await submit()
      await screen.findByRole('alert')

      await userEvent.clear(screen.getByLabelText('Usuario'))
      await userEvent.type(screen.getByLabelText('Usuario'), 'ana.rojas')
      await submit()

      expect(await screen.findByText('Vista del solicitante')).toBeInTheDocument()
    })

    it('warns when the network fails and lets the user try again', async () => {
      stubApi({
        [LOGIN]: () => {
          throw new TypeError('Failed to fetch')
        },
      })
      renderLogin()
      await fillIn('ana.rojas', 'cualquiera')

      await submit()

      expect(await screen.findByRole('alert')).toHaveTextContent('no pude abrir la compuerta')
      expect(screen.getByRole('button', { name: 'Ingresar' })).toBeEnabled()
      expect(getSession()).toBeNull()
    })

    it('warns in general terms when the API answers with a validation error', async () => {
      stubApi({ [LOGIN]: () => jsonResponse({ detail: [] }, 422) })
      renderLogin()
      await fillIn('ana.rojas', 'cualquiera')

      await submit()

      expect(await screen.findByRole('alert')).toHaveTextContent('no pude abrir la compuerta')
      expect(getSession()).toBeNull()
    })

    it('keeps what the user typed after a failure', async () => {
      stubApi({ [LOGIN]: () => jsonResponse({}, 500) })
      renderLogin()
      await fillIn('ana.rojas', 'cualquiera')

      await submit()

      await screen.findByRole('alert')
      expect(screen.getByLabelText('Usuario')).toHaveValue('ana.rojas')
      expect(screen.getByLabelText('Contraseña')).toHaveValue('cualquiera')
    })
  })
})
