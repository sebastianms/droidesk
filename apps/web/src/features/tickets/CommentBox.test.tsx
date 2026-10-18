import type { QueryClient } from '@tanstack/react-query'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createRef } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { $api } from '../../api/client'
import { ticketComment, ticketDetail } from '../../test/fixtures'
import { agentElena, jsonResponse, renderRoutes, requesterAna, signInAs, stubApi } from '../../test/helpers'
import { CommentBox } from './CommentBox'
import { COMMENT_MAX_LENGTH, COMMENT_REQUIRED, COMMENT_TOO_LONG } from './commentForm'
import type { TicketAction, TicketComment, TicketDetail, TicketView } from './types'

const COMMENT = 'POST /api/v1/tickets/42/comments'
const LIST = 'GET /api/v1/tickets'
const DETAIL_KEY = ['get', '/api/v1/tickets/{ticket_id}', { params: { path: { ticket_id: 42 } } }]
const EVERY_VIEW: TicketView[] = ['queue', 'assigned', 'mine']
const FIELD = 'Agregar un comentario'
const FIELD_REJECTION = {
  detail: [{ type: 'string_too_long', loc: ['body', 'body'], msg: 'Texto demasiado largo' }],
}

function renderBox(ticket: TicketDetail = ticketDetail(), user = requesterAna, replyTo?: TicketComment) {
  signInAs(user)
  const onReplyEnd = vi.fn()
  const box = <CommentBox ticket={ticket} replyTo={replyTo} inputRef={createRef()} onReplyEnd={onReplyEnd} />
  return { ...renderRoutes([{ path: '/', element: box }], '/'), onReplyEnd }
}

function ticketAllowing(...actions: TicketAction[]) {
  return ticketDetail({ allowed_actions: actions })
}

async function writeAndSend(text: string) {
  await userEvent.click(screen.getByLabelText(FIELD))
  await userEvent.paste(text)
  await userEvent.click(screen.getByRole('button', { name: 'Comentar' }))
}

async function cacheEveryList(queryClient: QueryClient) {
  for (const view of EVERY_VIEW) {
    await queryClient.prefetchQuery($api.queryOptions('get', '/api/v1/tickets', { params: { query: { view } } }))
  }
}

function requestedViews(fetchMock: ReturnType<typeof stubApi>) {
  return fetchMock.mock.calls
    .map(([request]) => request)
    .filter((request) => request.method === 'GET')
    .map((request) => new URL(request.url).searchParams.get('view'))
    .sort()
}

async function sentRequests(fetchMock: ReturnType<typeof stubApi>) {
  return Promise.all(
    fetchMock.mock.calls
      .map(([request]) => request)
      .filter((request) => request.method === 'POST')
      .map((request) => request.json()),
  )
}

async function sentBodies(fetchMock: ReturnType<typeof stubApi>) {
  return (await sentRequests(fetchMock)).map((request) => request.body)
}

describe('CommentBox', () => {
  describe('when it is offered', () => {
    it.each<[string, TicketAction[]]>([
      ['the requester of an open ticket', ['cancel', 'comment']],
      ['an agent', ['take', 'comment', 'change_priority']],
      ['the requester of a resolved ticket', ['close', 'reopen', 'comment']],
    ])('shows a field and the "Comentar" button for %s', (_who, actions) => {
      renderBox(ticketAllowing(...actions))

      expect(screen.getByLabelText(FIELD)).toBeVisible()
      expect(screen.getByRole('button', { name: 'Comentar' })).toBeEnabled()
    })

    it.each<[string, TicketAction[]]>([
      ['a ticket that allows no actions', []],
      ['a ticket that does not allow commenting', ['cancel', 'change_priority']],
    ])('shows nothing for %s', (_case, actions) => {
      renderBox(ticketAllowing(...actions))

      expect(screen.queryByLabelText(FIELD)).not.toBeInTheDocument()
      expect(screen.queryByRole('button')).not.toBeInTheDocument()
    })
  })

  describe('validation', () => {
    it.each([
      ['nothing', ''],
      ['only spaces and line breaks', ' \n\t  '],
    ])('asks for a text when the comment is %s, and sends nothing', async (_case, text) => {
      const fetchMock = stubApi({ [COMMENT]: () => jsonResponse(ticketDetail()) })
      renderBox()

      await writeAndSend(text)

      expect(await screen.findByText(COMMENT_REQUIRED)).toBeVisible()
      expect(fetchMock).not.toHaveBeenCalled()
    })

    it('moves the focus to the field and describes it with the error', async () => {
      stubApi({})
      renderBox()

      await userEvent.click(screen.getByRole('button', { name: 'Comentar' }))

      const field = screen.getByLabelText(FIELD)
      expect(field).toHaveFocus()
      expect(field).toBeInvalid()
      expect(field).toHaveAccessibleDescription(COMMENT_REQUIRED)
    })

    it('rejects a comment of more than 2.000 characters and sends nothing', async () => {
      const fetchMock = stubApi({ [COMMENT]: () => jsonResponse(ticketDetail()) })
      renderBox()

      await writeAndSend('a'.repeat(COMMENT_MAX_LENGTH + 1))

      expect(await screen.findByText(COMMENT_TOO_LONG)).toBeVisible()
      expect(fetchMock).not.toHaveBeenCalled()
    })

    it('counts characters, not UTF-16 units: 2.000 emoji go through', async () => {
      const fetchMock = stubApi({ [COMMENT]: () => jsonResponse(ticketDetail()) })
      renderBox()

      await writeAndSend('😀'.repeat(COMMENT_MAX_LENGTH))

      await waitFor(() => expect(fetchMock).toHaveBeenCalled())
      expect(screen.queryByText(COMMENT_TOO_LONG)).not.toBeInTheDocument()
    })

    it('clears the error as soon as the text changes', async () => {
      stubApi({})
      renderBox()
      await userEvent.click(screen.getByRole('button', { name: 'Comentar' }))
      await screen.findByText(COMMENT_REQUIRED)

      await userEvent.type(screen.getByLabelText(FIELD), 'H')

      expect(screen.queryByText(COMMENT_REQUIRED)).not.toBeInTheDocument()
    })
  })

  describe('sending', () => {
    it('sends the text of the comment without the spaces around it, to the ticket', async () => {
      const fetchMock = stubApi({ [COMMENT]: () => jsonResponse(ticketDetail()) })
      renderBox()

      await writeAndSend('  Hola\n\nGracias  ')

      await waitFor(() => expect(fetchMock).toHaveBeenCalled())
      expect(await sentBodies(fetchMock)).toEqual(['Hola\n\nGracias'])
    })

    it('keeps the ticket the API answers with', async () => {
      const updated = ticketDetail({ status: 'in_progress', allowed_actions: ['comment'] })
      stubApi({ [COMMENT]: () => jsonResponse(updated, 201) })
      const { queryClient } = renderBox()

      await writeAndSend('Hola')

      await waitFor(() => expect(queryClient.getQueryData(DETAIL_KEY)).toEqual(updated))
    })

    it('empties the field once the comment is in', async () => {
      stubApi({ [COMMENT]: () => jsonResponse(ticketDetail(), 201) })
      renderBox()

      await writeAndSend('Hola')

      await waitFor(() => expect(screen.getByLabelText(FIELD)).toHaveValue(''))
    })

    it('refreshes the queue, the assigned tickets and "Mis tickets", because the status may have changed', async () => {
      const fetchMock = stubApi({
        [LIST]: () => jsonResponse([]),
        [COMMENT]: () => jsonResponse(ticketDetail({ status: 'in_progress' }), 201),
      })
      const { queryClient } = renderBox()
      await cacheEveryList(queryClient)
      fetchMock.mockClear()

      await writeAndSend('Hola')

      await waitFor(() => expect(requestedViews(fetchMock)).toEqual(['assigned', 'mine', 'queue']))
    })

    it('is ready for another comment without waiting for the lists to refresh', async () => {
      let listRequests = 0
      stubApi({
        // Las lecturas que llenan la caché terminan; las que siguen al comentario no.
        [LIST]: () => (++listRequests <= EVERY_VIEW.length ? jsonResponse([]) : new Promise<Response>(() => {})),
        [COMMENT]: () => jsonResponse(ticketDetail(), 201),
      })
      const { queryClient } = renderBox()
      await cacheEveryList(queryClient)

      await writeAndSend('Hola')

      await waitFor(() => expect(screen.getByRole('button', { name: 'Comentar' })).toBeEnabled())
      expect(listRequests).toBeGreaterThan(EVERY_VIEW.length)
    })

    it('blocks the button while the comment is in flight', async () => {
      let finish: (response: Response) => void = () => {}
      stubApi({ [COMMENT]: () => new Promise<Response>((resolve) => (finish = resolve)) })
      renderBox()

      await writeAndSend('Hola')

      expect(screen.getByRole('button', { name: 'Comentando...' })).toBeDisabled()
      finish(jsonResponse(ticketDetail(), 201))
      await waitFor(() => expect(screen.getByRole('button', { name: 'Comentar' })).toBeEnabled())
    })

    it('lets an agent comment too', async () => {
      const fetchMock = stubApi({ [COMMENT]: () => jsonResponse(ticketDetail(), 201) })
      renderBox(ticketAllowing('comment'), agentElena)

      await writeAndSend('Necesito más datos')

      await waitFor(() => expect(fetchMock).toHaveBeenCalled())
      expect(await sentBodies(fetchMock)).toEqual(['Necesito más datos'])
    })
  })

  describe('replying to a comment', () => {
    const elena = { id: 5, name: 'Elena Vidal' }
    const original = ticketComment({ id: 7, author: elena, body: '¿Desde qué red te conectas?' })
    const NOT_REPLYING = /Respondiendo a/

    it('says who is being answered and shows the start of the comment above the field', () => {
      renderBox(ticketDetail(), requesterAna, original)

      const banner = screen.getByRole('status')
      expect(banner).toHaveTextContent('Respondiendo a Elena Vidal: «¿Desde qué red te conectas?»')
      expect(banner.compareDocumentPosition(screen.getByLabelText(FIELD))).toBe(Node.DOCUMENT_POSITION_FOLLOWING)
    })

    it('shows only the start of a long comment', () => {
      renderBox(ticketDetail(), requesterAna, ticketComment({ author: elena, body: `${'a'.repeat(120)}FIN` }))

      expect(screen.getByRole('status')).toHaveTextContent(`Respondiendo a Elena Vidal: «${'a'.repeat(120)}…»`)
    })

    it('shows the comment as text, without interpreting it', () => {
      const markup = '<img src=x onerror="alert(1)">'
      renderBox(ticketDetail(), requesterAna, ticketComment({ author: elena, body: markup }))

      expect(screen.getByRole('status')).toHaveTextContent(`«${markup}»`)
      expect(screen.queryByRole('img')).not.toBeInTheDocument()
    })

    it('says nothing when nobody is being answered', () => {
      renderBox()

      expect(screen.queryByText(NOT_REPLYING)).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: 'Cancelar respuesta' })).not.toBeInTheDocument()
    })

    it('does not show the answer when the ticket no longer allows commenting', () => {
      renderBox(ticketAllowing('cancel'), requesterAna, original)

      expect(screen.queryByText(NOT_REPLYING)).not.toBeInTheDocument()
    })

    it('stops answering when "Cancelar respuesta" is pressed, and leaves the focus on the field', async () => {
      const { onReplyEnd } = renderBox(ticketDetail(), requesterAna, original)

      await userEvent.click(screen.getByRole('button', { name: 'Cancelar respuesta' }))

      expect(onReplyEnd).toHaveBeenCalledOnce()
      expect(screen.getByLabelText(FIELD)).toHaveFocus()
    })

    it('keeps what was written when the answer is cancelled', async () => {
      renderBox(ticketDetail(), requesterAna, original)
      await userEvent.click(screen.getByLabelText(FIELD))
      await userEvent.paste('Borrador')

      await userEvent.click(screen.getByRole('button', { name: 'Cancelar respuesta' }))

      expect(screen.getByLabelText(FIELD)).toHaveValue('Borrador')
    })

    it('sends the comment as an answer to the one chosen', async () => {
      const fetchMock = stubApi({ [COMMENT]: () => jsonResponse(ticketDetail(), 201) })
      renderBox(ticketDetail(), requesterAna, original)

      await writeAndSend('Pruebo desde la red de la oficina')

      await waitFor(() => expect(fetchMock).toHaveBeenCalled())
      expect(await sentRequests(fetchMock)).toEqual([{ body: 'Pruebo desde la red de la oficina', reply_to_id: 7 }])
    })

    it('sends no reply when nobody is being answered', async () => {
      const fetchMock = stubApi({ [COMMENT]: () => jsonResponse(ticketDetail(), 201) })
      renderBox()

      await writeAndSend('Hola')

      await waitFor(() => expect(fetchMock).toHaveBeenCalled())
      expect(await sentRequests(fetchMock)).toEqual([{ body: 'Hola' }])
    })

    it('stops answering once the comment is published', async () => {
      stubApi({ [COMMENT]: () => jsonResponse(ticketDetail(), 201) })
      const { onReplyEnd } = renderBox(ticketDetail(), requesterAna, original)

      await writeAndSend('Hola')

      await waitFor(() => expect(onReplyEnd).toHaveBeenCalledOnce())
    })

    it.each([
      ['a conflict', jsonResponse({ code: 'action_not_allowed', message: 'Ya no se puede.' }, 409)],
      ['a failure', jsonResponse({ detail: 'boom' }, 500)],
      ['the rejection of the field', jsonResponse(FIELD_REJECTION, 422)],
    ])('keeps the answer after %s, so it can be sent again', async (_case, rejection) => {
      stubApi({ [LIST]: () => jsonResponse([]), [COMMENT]: () => rejection.clone() })
      const { onReplyEnd } = renderBox(ticketDetail(), requesterAna, original)

      await writeAndSend('Hola')

      await waitFor(() => expect(screen.getByRole('button', { name: 'Comentar' })).toBeEnabled())
      expect(onReplyEnd).not.toHaveBeenCalled()
      expect(screen.getByRole('status')).toHaveTextContent('Respondiendo a Elena Vidal')
    })
  })

  describe('a comment the API rejects', () => {
    it('shows the explanation of the API and keeps what was written', async () => {
      stubApi({
        [COMMENT]: () =>
          jsonResponse(
            {
              code: 'action_not_allowed',
              message: 'La acción «Comentar» no está disponible con el ticket en estado «Cerrado».',
            },
            409,
          ),
      })
      renderBox()

      await writeAndSend('Hola')

      expect(await screen.findByRole('alert')).toHaveTextContent('en estado «Cerrado»')
      expect(screen.getByLabelText(FIELD)).toHaveValue('Hola')
    })

    it('refreshes the detail and the lists, because the screen is out of date', async () => {
      stubApi({
        [LIST]: () => jsonResponse([]),
        [COMMENT]: () => jsonResponse({ code: 'action_not_allowed', message: 'Ya no se puede.' }, 409),
      })
      const { queryClient } = renderBox()
      const invalidate = vi.spyOn(queryClient, 'invalidateQueries')

      await writeAndSend('Hola')

      await waitFor(() => expect(invalidate).toHaveBeenCalledWith({ queryKey: DETAIL_KEY }))
    })

    it('shows a generic message when the failure has no explanation', async () => {
      stubApi({ [COMMENT]: () => jsonResponse({ detail: 'boom' }, 500) })
      renderBox()

      await writeAndSend('Hola')

      expect(await screen.findByRole('alert')).toHaveTextContent(
        'Bip-bup: no pude enviar el comentario. Intenta de nuevo.',
      )
    })

    it('puts a 422 on the field, with the focus, instead of a general notice', async () => {
      stubApi({ [COMMENT]: () => jsonResponse(FIELD_REJECTION, 422) })
      renderBox()

      await writeAndSend('Hola')

      expect(await screen.findByText('Texto demasiado largo')).toBeVisible()
      expect(screen.getByLabelText(FIELD)).toHaveFocus()
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })

    it('does not refresh anything for a 422 of the field, because the screen is not out of date', async () => {
      stubApi({ [COMMENT]: () => jsonResponse(FIELD_REJECTION, 422) })
      const { queryClient } = renderBox()
      const invalidate = vi.spyOn(queryClient, 'invalidateQueries')

      await writeAndSend('Hola')

      await screen.findByText('Texto demasiado largo')
      expect(invalidate).not.toHaveBeenCalled()
    })

    it('hides the message of the API as soon as the text changes', async () => {
      stubApi({ [COMMENT]: () => jsonResponse(FIELD_REJECTION, 422) })
      renderBox()
      await writeAndSend('Hola')
      await screen.findByText('Texto demasiado largo')

      await userEvent.type(screen.getByLabelText(FIELD), '!')

      expect(screen.queryByText('Texto demasiado largo')).not.toBeInTheDocument()
    })

    it('hides the notice of a failure as soon as the text changes', async () => {
      stubApi({ [COMMENT]: () => jsonResponse({ detail: 'boom' }, 500) })
      renderBox()
      await writeAndSend('Hola')
      await screen.findByRole('alert')

      await userEvent.type(screen.getByLabelText(FIELD), '!')

      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })

    it('clears the failure when the next attempt goes through', async () => {
      let attempts = 0
      stubApi({
        [COMMENT]: () => (++attempts === 1 ? jsonResponse({ detail: 'boom' }, 500) : jsonResponse(ticketDetail(), 201)),
      })
      renderBox()
      await writeAndSend('Hola')
      await screen.findByRole('alert')

      await userEvent.click(screen.getByRole('button', { name: 'Comentar' }))

      await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
    })
  })
})
