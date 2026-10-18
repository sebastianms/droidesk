import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { ticketComment, ticketDetail } from '../../test/fixtures'
import { jsonResponse, renderRoutes, requesterAna, signInAs, stubApi } from '../../test/helpers'
import { Conversation } from './Conversation'
import type { TicketDetail } from './types'

const COMMENT = 'POST /api/v1/tickets/42/comments'
const LIST = 'GET /api/v1/tickets'
const FIELD = 'Agregar un comentario'
const elena = { id: 5, name: 'Elena Vidal' }
const QUESTION = '¿Desde qué red te conectas?'
const ANSWER = 'Desde la red de la oficina.'
const question = ticketComment({ id: 1, author: elena, body: QUESTION })

function renderConversation(ticket: TicketDetail) {
  signInAs(requesterAna)
  return renderRoutes([{ path: '/', element: <Conversation ticket={ticket} /> }], '/')
}

function ticketWithQuestion(overrides: Partial<TicketDetail> = {}) {
  return ticketDetail({ allowed_actions: ['comment'], comments: [question], ...overrides })
}

async function replyToElena() {
  await userEvent.click(screen.getByRole('button', { name: 'Responder a Elena Vidal' }))
}

async function write(text: string) {
  await userEvent.click(screen.getByLabelText(FIELD))
  await userEvent.paste(text)
}

describe('Conversation', () => {
  describe('choosing whom to answer', () => {
    it('offers "Responder" on each comment when the ticket allows commenting', () => {
      renderConversation(ticketWithQuestion())

      expect(screen.getByRole('button', { name: 'Responder a Elena Vidal' })).toBeVisible()
    })

    it('offers no "Responder" when the ticket does not allow commenting', () => {
      renderConversation(ticketWithQuestion({ status: 'closed', allowed_actions: [] }))

      expect(screen.getByText(QUESTION)).toBeVisible()
      expect(screen.queryByRole('button', { name: /^Responder/ })).not.toBeInTheDocument()
    })

    it('shows whom is being answered and moves the focus to the field', async () => {
      renderConversation(ticketWithQuestion())

      await replyToElena()

      expect(screen.getByRole('status')).toHaveTextContent(`Respondiendo a Elena Vidal: «${QUESTION}»`)
      expect(screen.getByLabelText(FIELD)).toHaveFocus()
    })

    it('moves the focus to the field again when the same comment is chosen once more', async () => {
      renderConversation(ticketWithQuestion())
      await replyToElena()
      screen.getByRole('button', { name: 'Responder a Elena Vidal' }).focus()

      await userEvent.keyboard('{Enter}')

      expect(screen.getByLabelText(FIELD)).toHaveFocus()
    })

    it('answers only the last comment chosen', async () => {
      const own = ticketComment({ id: 2, body: 'Sigue sin funcionar' })
      renderConversation(ticketWithQuestion({ comments: [question, own] }))
      await replyToElena()

      await userEvent.click(screen.getByRole('button', { name: 'Responder a Ana Rojas' }))

      expect(screen.getByRole('status')).toHaveTextContent('Respondiendo a Ana Rojas: «Sigue sin funcionar»')
    })

    it('keeps what was written when another comment is chosen', async () => {
      const own = ticketComment({ id: 2, body: 'Sigue sin funcionar' })
      renderConversation(ticketWithQuestion({ comments: [question, own] }))
      await write('Borrador')

      await replyToElena()

      expect(screen.getByLabelText(FIELD)).toHaveValue('Borrador')
    })

    it('stops answering when the reply is cancelled', async () => {
      renderConversation(ticketWithQuestion())
      await replyToElena()

      await userEvent.click(screen.getByRole('button', { name: 'Cancelar respuesta' }))

      expect(screen.queryByText(/Respondiendo a/)).not.toBeInTheDocument()
      expect(screen.getByLabelText(FIELD)).toHaveFocus()
    })
  })

  describe('publishing the answer', () => {
    const answered = ticketComment({ id: 2, body: ANSWER, reply_to_id: 1 })
    const updated = ticketWithQuestion({ comments: [question, answered] })

    it('sends it as an answer to the comment chosen', async () => {
      let sent: unknown
      stubApi({
        [LIST]: () => jsonResponse([]),
        [COMMENT]: async (request) => {
          sent = await request.json()
          return jsonResponse(updated, 201)
        },
      })
      renderConversation(ticketWithQuestion())
      await replyToElena()
      await write(ANSWER)

      await userEvent.click(screen.getByRole('button', { name: 'Comentar' }))

      await waitFor(() => expect(sent).toEqual({ body: ANSWER, reply_to_id: 1 }))
    })

    it('clears the answer and the field once it is published', async () => {
      stubApi({ [LIST]: () => jsonResponse([]), [COMMENT]: () => jsonResponse(updated, 201) })
      renderConversation(ticketWithQuestion())
      await replyToElena()
      await write(ANSWER)

      await userEvent.click(screen.getByRole('button', { name: 'Comentar' }))

      await waitFor(() => expect(screen.queryByText(/Respondiendo a/)).not.toBeInTheDocument())
      expect(screen.getByLabelText(FIELD)).toHaveValue('')
    })

    it('keeps the answer when the comment is rejected', async () => {
      stubApi({ [COMMENT]: () => jsonResponse({ detail: 'boom' }, 500) })
      renderConversation(ticketWithQuestion())
      await replyToElena()
      await write(ANSWER)

      await userEvent.click(screen.getByRole('button', { name: 'Comentar' }))

      expect(await screen.findByRole('alert')).toBeVisible()
      expect(screen.getByRole('status')).toHaveTextContent('Respondiendo a Elena Vidal')
      expect(screen.getByLabelText(FIELD)).toHaveValue(ANSWER)
    })
  })
})
