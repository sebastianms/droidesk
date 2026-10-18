import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { categories, slaPolicies, ticketDetail, ticketSummary } from '../../test/fixtures'
import { jsonResponse, renderRoutes, requesterAna, signInAs, stubApi } from '../../test/helpers'
import { MyTicketsPage } from './MyTicketsPage'
import { NewTicketForm } from './NewTicketForm'
import {
  CATEGORY_REQUIRED,
  DESCRIPTION_REQUIRED,
  DESCRIPTION_TOO_LONG,
  TITLE_MAX_LENGTH,
  TITLE_REQUIRED,
  TITLE_TOO_LONG,
} from './ticketForm'

const CATEGORIES = 'GET /api/v1/categories'
const POLICIES = 'GET /api/v1/sla-policies'
const CREATE = 'POST /api/v1/tickets'
const LIST = 'GET /api/v1/tickets'

const OPTIONS = { [CATEGORIES]: () => jsonResponse(categories), [POLICIES]: () => jsonResponse(slaPolicies) }

function renderForm() {
  signInAs(requesterAna)
  return renderRoutes(
    [
      { path: '/requester/new', element: <NewTicketForm /> },
      { path: '/requester', element: <p>Vista Mis tickets</p> },
    ],
    '/requester/new',
  )
}

async function renderLoadedForm() {
  const rendered = renderForm()
  await screen.findByLabelText('Título')
  return rendered
}

async function fillIn({ title = '', description = '', category = '' } = {}) {
  if (title) await userEvent.type(screen.getByLabelText('Título'), title)
  if (description) await userEvent.type(screen.getByLabelText('Descripción'), description)
  if (category) await userEvent.selectOptions(screen.getByLabelText('Categoría'), category)
}

async function submit() {
  await userEvent.click(screen.getByRole('button', { name: 'Crear ticket' }))
}

function postedBodies(fetchMock: ReturnType<typeof stubApi>) {
  return Promise.all(
    fetchMock.mock.calls
      .map(([request]) => request)
      .filter((r) => r.method === 'POST')
      .map((r) => r.json()),
  )
}

describe('NewTicketForm', () => {
  describe('options', () => {
    it('offers the categories and the priorities of the API', async () => {
      stubApi(OPTIONS)

      await renderLoadedForm()

      expect(screen.getByRole('heading', { name: 'Nuevo ticket' })).toBeVisible()
      expect(
        within(screen.getByLabelText('Categoría'))
          .getAllByRole('option')
          .map((o) => o.textContent),
      ).toEqual(['Elige una categoría', 'Hardware', 'Software', 'Accesos y cuentas', 'Red y conectividad'])
      expect(
        within(screen.getByLabelText('Prioridad'))
          .getAllByRole('option')
          .map((o) => o.textContent),
      ).toEqual(['Crítica', 'Alta', 'Media', 'Baja'])
    })

    it('says it is preparing the form until the options arrive', async () => {
      stubApi(OPTIONS)

      renderForm()

      expect(screen.getByRole('status')).toHaveTextContent('Bip-bup: preparando el formulario...')
      await screen.findByLabelText('Título')
      expect(screen.queryByRole('status')).not.toBeInTheDocument()
    })

    it('preselects the medium priority and explains it', async () => {
      stubApi(OPTIONS)

      await renderLoadedForm()

      const priority = screen.getByLabelText('Prioridad')
      expect(priority).toHaveValue('medium')
      expect(priority).toHaveAccessibleDescription(slaPolicies[2].description)
    })

    it('explains the priority the requester picks', async () => {
      stubApi(OPTIONS)
      await renderLoadedForm()

      await userEvent.selectOptions(screen.getByLabelText('Prioridad'), 'Crítica')

      expect(screen.getByLabelText('Prioridad')).toHaveValue('critical')
      expect(screen.getByLabelText('Prioridad')).toHaveAccessibleDescription(slaPolicies[0].description)
    })

    it('shows the failure and no form when the options cannot be loaded', async () => {
      stubApi({
        [CATEGORIES]: () => jsonResponse({ detail: 'boom' }, 500),
        [POLICIES]: () => jsonResponse(slaPolicies),
      })

      renderForm()

      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Bip-bup: no pude preparar el formulario. Intenta de nuevo.',
      )
      expect(screen.queryByLabelText('Título')).not.toBeInTheDocument()
    })

    it('shows the message of the API when the priorities cannot be loaded', async () => {
      stubApi({
        [CATEGORIES]: () => jsonResponse(categories),
        [POLICIES]: () => jsonResponse({ code: 'forbidden', message: 'No puedes ver las prioridades.' }, 403),
      })

      renderForm()

      expect(await screen.findByRole('alert')).toHaveTextContent('No puedes ver las prioridades.')
    })
  })

  describe('validation', () => {
    it('says what is missing and sends nothing', async () => {
      const fetchMock = stubApi({ ...OPTIONS, [CREATE]: () => jsonResponse(ticketDetail(), 201) })
      await renderLoadedForm()

      await submit()

      expect(screen.getByLabelText('Título')).toHaveAccessibleDescription(TITLE_REQUIRED)
      expect(screen.getByLabelText('Descripción')).toHaveAccessibleDescription(DESCRIPTION_REQUIRED)
      expect(screen.getByLabelText('Categoría')).toHaveAccessibleDescription(CATEGORY_REQUIRED)
      expect(await postedBodies(fetchMock)).toEqual([])
    })

    it('marks the fields with a complaint as invalid', async () => {
      stubApi(OPTIONS)
      await renderLoadedForm()
      await fillIn({ title: 'Monitor' })

      await submit()

      expect(screen.getByLabelText('Título')).not.toHaveAttribute('aria-invalid')
      expect(screen.getByLabelText('Descripción')).toHaveAttribute('aria-invalid', 'true')
      expect(screen.getByLabelText('Categoría')).toHaveAttribute('aria-invalid', 'true')
    })

    it.each([
      ['title', 'Título'],
      ['description', 'Descripción'],
    ])('treats a %s of only spaces as empty', async (field, label) => {
      stubApi(OPTIONS)
      await renderLoadedForm()
      await userEvent.type(screen.getByLabelText(label), '   ')

      await submit()

      expect(screen.getByLabelText(label)).toHaveAttribute('aria-invalid', 'true')
      expect(field).toBeTruthy()
    })

    it('moves the focus to the title when it is the first with a complaint', async () => {
      stubApi(OPTIONS)
      await renderLoadedForm()

      await submit()

      expect(screen.getByLabelText('Título')).toHaveFocus()
    })

    it('moves the focus to the description when the title is fine', async () => {
      stubApi(OPTIONS)
      await renderLoadedForm()
      await fillIn({ title: 'Monitor' })

      await submit()

      expect(screen.getByLabelText('Descripción')).toHaveFocus()
    })

    it('moves the focus to the category when it is the only one missing', async () => {
      stubApi(OPTIONS)
      await renderLoadedForm()
      await fillIn({ title: 'Monitor', description: 'Pantalla negra' })

      await submit()

      expect(screen.getByLabelText('Categoría')).toHaveFocus()
    })

    it('rejects a title one character over the limit', async () => {
      stubApi(OPTIONS)
      await renderLoadedForm()
      await userEvent.click(screen.getByLabelText('Título'))
      await userEvent.paste('a'.repeat(TITLE_MAX_LENGTH + 1))
      await fillIn({ description: 'Pantalla negra', category: 'Hardware' })

      await submit()

      expect(screen.getByLabelText('Título')).toHaveAccessibleDescription(TITLE_TOO_LONG)
    })

    it('rejects a description over the limit', async () => {
      stubApi(OPTIONS)
      await renderLoadedForm()
      await userEvent.click(screen.getByLabelText('Descripción'))
      await userEvent.paste('a'.repeat(5001))
      await fillIn({ title: 'Monitor', category: 'Hardware' })

      await submit()

      expect(screen.getByLabelText('Descripción')).toHaveAccessibleDescription(DESCRIPTION_TOO_LONG)
    })

    it.each([
      ['Título', 'Monitor'],
      ['Descripción', 'Pantalla negra'],
    ])('clears the complaint about the %s as soon as it is edited', async (label, text) => {
      stubApi(OPTIONS)
      await renderLoadedForm()
      await submit()

      await userEvent.type(screen.getByLabelText(label), text)

      expect(screen.getByLabelText(label)).not.toHaveAttribute('aria-invalid')
      expect(screen.getByLabelText(label)).not.toHaveAccessibleDescription()
    })

    it('clears the complaint about the category as soon as one is picked', async () => {
      stubApi(OPTIONS)
      await renderLoadedForm()
      await submit()

      await userEvent.selectOptions(screen.getByLabelText('Categoría'), 'Software')

      expect(screen.getByLabelText('Categoría')).not.toHaveAttribute('aria-invalid')
    })
  })

  describe('creation', () => {
    it('sends the trimmed text, the category and the priority', async () => {
      const fetchMock = stubApi({ ...OPTIONS, [CREATE]: () => jsonResponse(ticketDetail(), 201) })
      await renderLoadedForm()
      await fillIn({ title: '  No enciende el monitor  ', description: ' Pantalla negra ', category: 'Software' })
      await userEvent.selectOptions(screen.getByLabelText('Prioridad'), 'Alta')

      await submit()

      await waitFor(async () =>
        expect(await postedBodies(fetchMock)).toEqual([
          { title: 'No enciende el monitor', description: 'Pantalla negra', category_id: 2, priority: 'high' },
        ]),
      )
    })

    it('sends the medium priority when the requester does not change it', async () => {
      const fetchMock = stubApi({ ...OPTIONS, [CREATE]: () => jsonResponse(ticketDetail(), 201) })
      await renderLoadedForm()
      await fillIn({ title: 'Monitor', description: 'Pantalla negra', category: 'Hardware' })

      await submit()

      await waitFor(async () => expect(await postedBodies(fetchMock)).toMatchObject([{ priority: 'medium' }]))
    })

    it('takes the requester to "Mis tickets" once the ticket is created', async () => {
      stubApi({ ...OPTIONS, [CREATE]: () => jsonResponse(ticketDetail(), 201) })
      const { router } = await renderLoadedForm()
      await fillIn({ title: 'Monitor', description: 'Pantalla negra', category: 'Hardware' })

      await submit()

      expect(await screen.findByText('Vista Mis tickets')).toBeVisible()
      expect(router.state.location.pathname).toBe('/requester')
    })

    it('waits for the refreshed list before leaving, so the new ticket is already there', async () => {
      let listRequests = 0
      let releaseList = () => {}
      stubApi({
        ...OPTIONS,
        [CREATE]: () => jsonResponse(ticketDetail(), 201),
        [LIST]: () => {
          listRequests += 1
          if (listRequests === 1) return jsonResponse([])
          return new Promise<Response>((resolve) => {
            releaseList = () => resolve(jsonResponse([ticketSummary({ title: 'Monitor sin imagen' })]))
          })
        },
      })
      signInAs(requesterAna)
      renderRoutes(
        [
          { path: '/requester', element: <MyTicketsPage /> },
          { path: '/requester/new', element: <NewTicketForm /> },
        ],
        '/requester',
      )
      await userEvent.click(await screen.findByRole('link', { name: 'Nuevo ticket' }))
      await screen.findByLabelText('Título')
      await fillIn({ title: 'Monitor sin imagen', description: 'Pantalla negra', category: 'Hardware' })

      await submit()

      await waitFor(() => expect(listRequests).toBe(2))
      expect(screen.getByRole('heading', { name: 'Nuevo ticket' })).toBeVisible()
      releaseList()
      expect(await screen.findByRole('link', { name: 'Monitor sin imagen' })).toBeVisible()
    })

    it('blocks a second send while the first is in flight', async () => {
      let finish: (response: Response) => void = () => {}
      stubApi({ ...OPTIONS, [CREATE]: () => new Promise<Response>((resolve) => (finish = resolve)) })
      await renderLoadedForm()
      await fillIn({ title: 'Monitor', description: 'Pantalla negra', category: 'Hardware' })

      await submit()

      expect(await screen.findByRole('button', { name: 'Creando...' })).toBeDisabled()
      finish(jsonResponse(ticketDetail(), 201))
      await screen.findByText('Vista Mis tickets')
    })

    it('goes back to "Mis tickets" without creating anything', async () => {
      const fetchMock = stubApi(OPTIONS)
      const { router } = await renderLoadedForm()

      await userEvent.click(screen.getByRole('link', { name: 'Cancelar' }))

      expect(await screen.findByText('Vista Mis tickets')).toBeVisible()
      expect(router.state.location.pathname).toBe('/requester')
      expect(await postedBodies(fetchMock)).toEqual([])
    })
  })

  describe('server rejections', () => {
    it('shows the complaint of the API next to the field it names and moves the focus there', async () => {
      stubApi({
        ...OPTIONS,
        [CREATE]: () =>
          jsonResponse(
            { detail: [{ type: 'value_error', loc: ['body', 'category_id'], msg: 'La categoría no existe.' }] },
            422,
          ),
      })
      await renderLoadedForm()
      await fillIn({ title: 'Monitor', description: 'Pantalla negra', category: 'Hardware' })

      await submit()

      const category = await screen.findByLabelText('Categoría')
      await waitFor(() => expect(category).toHaveAccessibleDescription('La categoría no existe.'))
      expect(category).toHaveFocus()
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })

    it('keeps what the requester wrote when the API rejects the ticket', async () => {
      stubApi({
        ...OPTIONS,
        [CREATE]: () => jsonResponse({ detail: [{ type: 'x', loc: ['body', 'title'], msg: 'Rechazado.' }] }, 422),
      })
      await renderLoadedForm()
      await fillIn({ title: 'Monitor', description: 'Pantalla negra', category: 'Hardware' })

      await submit()

      await waitFor(() => expect(screen.getByLabelText('Título')).toHaveAccessibleDescription('Rechazado.'))
      expect(screen.getByLabelText('Descripción')).toHaveValue('Pantalla negra')
      expect(screen.getByLabelText('Categoría')).toHaveValue('1')
    })

    it('shows the message of the API when it refuses the ticket for another reason', async () => {
      stubApi({
        ...OPTIONS,
        [CREATE]: () => jsonResponse({ code: 'forbidden', message: 'Tu perfil no puede crear tickets.' }, 403),
      })
      await renderLoadedForm()
      await fillIn({ title: 'Monitor', description: 'Pantalla negra', category: 'Hardware' })

      await submit()

      expect(await screen.findByRole('alert')).toHaveTextContent('Tu perfil no puede crear tickets.')
      expect(screen.getByRole('button', { name: 'Crear ticket' })).toBeEnabled()
    })

    it('shows a generic message when the failure has no explanation', async () => {
      stubApi({ ...OPTIONS, [CREATE]: () => jsonResponse({ detail: 'boom' }, 500) })
      await renderLoadedForm()
      await fillIn({ title: 'Monitor', description: 'Pantalla negra', category: 'Hardware' })

      await submit()

      expect(await screen.findByRole('alert')).toHaveTextContent('Bip-bup: no pude crear el ticket. Intenta de nuevo.')
    })
  })
})
