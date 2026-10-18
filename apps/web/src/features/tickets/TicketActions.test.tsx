import { fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ticketDetail } from '../../test/fixtures'
import { jsonResponse, renderRoutes, requesterAna, signInAs, stubApi } from '../../test/helpers'
import { TicketActions } from './TicketActions'
import type { TicketAction, TicketDetail } from './types'

const TRANSITION = 'POST /api/v1/tickets/42/transitions'
const DETAIL_KEY = ['get', '/api/v1/tickets/{ticket_id}', { params: { path: { ticket_id: 42 } } }]
const LIST_KEY = ['get', '/api/v1/tickets']

function renderActions(ticket: TicketDetail) {
  signInAs(requesterAna)
  return renderRoutes([{ path: '/', element: <TicketActions ticket={ticket} /> }], '/')
}

function ticketAllowing(...actions: TicketAction[]) {
  return ticketDetail({ allowed_actions: actions })
}

function buttonNames() {
  return screen.queryAllByRole('button').map((button) => button.textContent)
}

function sentActions(fetchMock: ReturnType<typeof stubApi>) {
  return Promise.all(
    fetchMock.mock.calls
      .map(([request]) => request)
      .filter((request) => request.method === 'POST')
      .map(async (request) => (await request.json()).action),
  )
}

describe('TicketActions', () => {
  describe('buttons', () => {
    it.each<[TicketAction, string]>([
      ['take', 'Tomar'],
      ['cancel', 'Cancelar'],
      ['hold', 'Dejar en espera'],
      ['resume', 'Retomar'],
      ['resolve', 'Resolver'],
      ['close', 'Confirmar cierre'],
      ['reopen', 'Reabrir'],
    ])('offers %s as a button when the API allows it', (action, label) => {
      renderActions(ticketAllowing(action))

      expect(screen.getByRole('button', { name: label })).toBeEnabled()
    })

    it('offers exactly the actions the API allows, in its order', () => {
      renderActions(ticketAllowing('resolve', 'hold'))

      expect(buttonNames()).toEqual(['Resolver', 'Dejar en espera'])
    })

    it('does not offer what the API does not allow', () => {
      renderActions(ticketAllowing('cancel'))

      expect(buttonNames()).toEqual(['Cancelar'])
    })

    it('does not make buttons out of comment and change_priority, which are not transitions yet', () => {
      renderActions(ticketAllowing('cancel', 'comment', 'change_priority'))

      expect(buttonNames()).toEqual(['Cancelar'])
    })

    it.each([
      ['no actions', []],
      ['only actions that are not transitions', ['comment', 'change_priority']],
    ] as [string, TicketAction[]][])('shows nothing at all with %s', (_case, actions) => {
      renderActions(ticketAllowing(...actions))

      expect(screen.queryByRole('region', { name: 'Acciones' })).not.toBeInTheDocument()
      expect(buttonNames()).toEqual([])
    })
  })

  describe('a transition', () => {
    it('asks the API for the action and keeps the ticket it answers with', async () => {
      const updated = ticketDetail({ status: 'resolved', allowed_actions: ['close', 'reopen'] })
      const fetchMock = stubApi({ [TRANSITION]: () => jsonResponse(updated) })
      const { queryClient } = renderActions(ticketAllowing('resolve'))

      await userEvent.click(screen.getByRole('button', { name: 'Resolver' }))

      await waitFor(() => expect(queryClient.getQueryData(DETAIL_KEY)).toEqual(updated))
      expect(await sentActions(fetchMock)).toEqual(['resolve'])
    })

    it('refreshes the lists, which show the old status', async () => {
      stubApi({ [TRANSITION]: () => jsonResponse(ticketDetail({ status: 'resolved' })) })
      const { queryClient } = renderActions(ticketAllowing('resolve'))
      const invalidate = vi.spyOn(queryClient, 'invalidateQueries')

      await userEvent.click(screen.getByRole('button', { name: 'Resolver' }))

      await waitFor(() => expect(invalidate).toHaveBeenCalledWith(expect.objectContaining({ queryKey: LIST_KEY })))
    })

    it('refreshes the detail when the change is rejected, because the screen is out of date', async () => {
      stubApi({ [TRANSITION]: () => jsonResponse({ code: 'action_not_allowed', message: 'Ya no se puede.' }, 409) })
      const { queryClient } = renderActions(ticketAllowing('resolve'))
      const invalidate = vi.spyOn(queryClient, 'invalidateQueries')

      await userEvent.click(screen.getByRole('button', { name: 'Resolver' }))

      await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: DETAIL_KEY }))
    })

    it('blocks the buttons while the change is in flight', async () => {
      let finish: (response: Response) => void = () => {}
      stubApi({ [TRANSITION]: () => new Promise<Response>((resolve) => (finish = resolve)) })
      renderActions(ticketAllowing('hold', 'resolve'))

      await userEvent.click(screen.getByRole('button', { name: 'Resolver' }))

      expect(screen.getByRole('button', { name: 'Resolver' })).toBeDisabled()
      expect(screen.getByRole('button', { name: 'Dejar en espera' })).toBeDisabled()
      finish(jsonResponse(ticketDetail()))
      await waitFor(() => expect(screen.getByRole('button', { name: 'Resolver' })).toBeEnabled())
    })

    it('shows the explanation of the API when the change is no longer possible', async () => {
      stubApi({
        [TRANSITION]: () => jsonResponse({ code: 'action_not_allowed', message: 'El ticket ya fue tomado.' }, 409),
      })
      renderActions(ticketAllowing('cancel'))

      await userEvent.click(screen.getByRole('button', { name: 'Cancelar' }))
      await userEvent.click(screen.getByRole('button', { name: 'Sí, cancelar ticket' }))

      expect(await screen.findByRole('alert')).toHaveTextContent('El ticket ya fue tomado.')
      expect(screen.getByRole('button', { name: 'Cancelar' })).toBeEnabled()
    })

    it('shows a generic message when the failure has no explanation', async () => {
      stubApi({ [TRANSITION]: () => jsonResponse({ detail: 'boom' }, 500) })
      renderActions(ticketAllowing('resolve'))

      await userEvent.click(screen.getByRole('button', { name: 'Resolver' }))

      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Bip-bup: no pude aplicar el cambio. Intenta de nuevo.',
      )
    })

    it('clears the failure when the next attempt goes through', async () => {
      let attempts = 0
      stubApi({
        [TRANSITION]: () => (++attempts === 1 ? jsonResponse({ detail: 'boom' }, 500) : jsonResponse(ticketDetail())),
      })
      renderActions(ticketAllowing('resolve'))
      await userEvent.click(screen.getByRole('button', { name: 'Resolver' }))
      await screen.findByRole('alert')

      await userEvent.click(screen.getByRole('button', { name: 'Resolver' }))

      await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
    })
  })

  describe('cancelling', () => {
    it('asks for confirmation before cancelling, and sends nothing yet', async () => {
      const fetchMock = stubApi({ [TRANSITION]: () => jsonResponse(ticketDetail()) })
      renderActions(ticketAllowing('cancel'))

      await userEvent.click(screen.getByRole('button', { name: 'Cancelar' }))

      const dialog = screen.getByRole('dialog', { name: 'Cancelar ticket' })
      expect(dialog).toHaveAccessibleDescription(/no se puede deshacer/)
      expect(fetchMock).not.toHaveBeenCalled()
    })

    it('cancels once the requester confirms', async () => {
      const cancelled = ticketDetail({ status: 'cancelled', allowed_actions: [] })
      const fetchMock = stubApi({ [TRANSITION]: () => jsonResponse(cancelled) })
      const { queryClient } = renderActions(ticketAllowing('cancel'))
      await userEvent.click(screen.getByRole('button', { name: 'Cancelar' }))

      await userEvent.click(screen.getByRole('button', { name: 'Sí, cancelar ticket' }))

      await waitFor(() => expect(queryClient.getQueryData(DETAIL_KEY)).toEqual(cancelled))
      expect(await sentActions(fetchMock)).toEqual(['cancel'])
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    it('keeps the ticket when the requester changes their mind', async () => {
      const fetchMock = stubApi({ [TRANSITION]: () => jsonResponse(ticketDetail()) })
      renderActions(ticketAllowing('cancel'))
      await userEvent.click(screen.getByRole('button', { name: 'Cancelar' }))

      await userEvent.click(screen.getByRole('button', { name: 'No, volver' }))

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(fetchMock).not.toHaveBeenCalled()
    })

    it('keeps the ticket when the dialog is dismissed with Escape', async () => {
      const fetchMock = stubApi({ [TRANSITION]: () => jsonResponse(ticketDetail()) })
      renderActions(ticketAllowing('cancel'))
      await userEvent.click(screen.getByRole('button', { name: 'Cancelar' }))

      fireEvent(screen.getByRole('dialog'), new Event('cancel', { cancelable: true }))

      await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
      expect(fetchMock).not.toHaveBeenCalled()
    })

    it('does not ask for confirmation to take another action', async () => {
      stubApi({ [TRANSITION]: () => jsonResponse(ticketDetail()) })
      renderActions(ticketAllowing('cancel', 'hold'))

      await userEvent.click(screen.getByRole('button', { name: 'Dejar en espera' }))

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
  })
})
