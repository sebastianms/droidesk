import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ticketComment } from '../../test/fixtures'
import { CommentList } from './CommentList'
import { formatDateTime } from './dates'
import { EXCERPT_LENGTH } from './excerpt'

const elena = { id: 5, name: 'Elena Vidal' }
const ORIGINAL = 'Probé con otra red y sigue igual.'

describe('CommentList', () => {
  it('says there are no comments yet', () => {
    render(<CommentList comments={[]} />)

    expect(screen.getByText('Sin comentarios todavía.')).toBeVisible()
    expect(screen.queryByRole('list')).not.toBeInTheDocument()
  })

  it('shows each comment with its author, its text and its local date and time', () => {
    render(<CommentList comments={[ticketComment()]} />)

    const item = within(screen.getByRole('listitem'))
    expect(item.getByText('Ana Rojas')).toBeVisible()
    expect(item.getByText('La VPN sigue rechazando mis credenciales.')).toBeVisible()
    expect(item.getByText(formatDateTime('2026-10-19T13:05:00Z'))).toHaveAttribute('datetime', '2026-10-19T13:05:00Z')
  })

  it('lists the comments in the order the API gives them', () => {
    const comments = [
      ticketComment({ id: 1, body: 'Primero' }),
      ticketComment({ id: 2, body: 'Segundo', author: { id: 5, name: 'Elena Vidal' } }),
      ticketComment({ id: 3, body: 'Tercero' }),
    ]

    render(<CommentList comments={comments} />)

    const when = formatDateTime('2026-10-19T13:05:00Z')
    expect(screen.getAllByRole('listitem').map((item) => item.textContent)).toEqual([
      `Ana RojasPrimero${when}`,
      `Elena VidalSegundo${when}`,
      `Ana RojasTercero${when}`,
    ])
  })

  it('shows the text as it is, without interpreting it as HTML', () => {
    const markup = '<img src=x onerror="alert(1)"> <b>negrita</b> **negrita** &amp;'

    render(<CommentList comments={[ticketComment({ body: markup })]} />)

    expect(screen.getByText(markup)).toBeVisible()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(document.querySelector('b')).toBeNull()
  })

  it('keeps the line breaks of the text', () => {
    render(<CommentList comments={[ticketComment({ body: 'Línea 1\n\n  Línea 2' })]} />)

    expect(screen.getByText(/Línea 1/).textContent).toBe('Línea 1\n\n  Línea 2')
  })

  it('shows an author name with markup as text', () => {
    render(<CommentList comments={[ticketComment({ author: { id: 9, name: '<b>Eva</b>' } })]} />)

    expect(screen.getByText('<b>Eva</b>')).toBeVisible()
  })

  it('gives each comment an anchor to link to', () => {
    render(<CommentList comments={[ticketComment({ id: 1 }), ticketComment({ id: 7 })]} />)

    expect(screen.getAllByRole('listitem').map((item) => item.id)).toEqual(['comment-1', 'comment-7'])
  })

  describe('replying', () => {
    it('offers "Responder" on every comment, named after its author', () => {
      const comments = [ticketComment({ id: 1 }), ticketComment({ id: 2, author: elena })]

      render(<CommentList comments={comments} onReply={() => {}} />)

      expect(screen.getByRole('button', { name: 'Responder a Ana Rojas' })).toHaveTextContent('Responder')
      expect(screen.getByRole('button', { name: 'Responder a Elena Vidal' })).toHaveTextContent('Responder')
    })

    it('hands the comment to answer to the one who listens', async () => {
      const onReply = vi.fn()
      const comments = [ticketComment({ id: 1 }), ticketComment({ id: 2, author: elena })]
      render(<CommentList comments={comments} onReply={onReply} />)

      await userEvent.click(screen.getByRole('button', { name: 'Responder a Elena Vidal' }))

      expect(onReply).toHaveBeenCalledExactlyOnceWith(comments[1])
    })

    it('offers nothing when nobody can reply', () => {
      render(<CommentList comments={[ticketComment()]} />)

      expect(screen.queryByRole('button')).not.toBeInTheDocument()
    })
  })

  describe('a comment that answers another', () => {
    const original = ticketComment({ id: 1, author: elena, body: ORIGINAL })
    const answer = ticketComment({ id: 2, body: 'Gracias, lo reviso.', reply_to_id: 1 })

    it('shows the author and the text of the original above its own text, with a link to it', () => {
      render(<CommentList comments={[original, answer]} />)

      const item = within(screen.getAllByRole('listitem')[1])
      const quote = within(item.getByRole('blockquote'))
      expect(quote.getByText('Elena Vidal')).toBeVisible()
      expect(quote.getByText(ORIGINAL)).toBeVisible()
      expect(item.getByRole('link', { name: 'Ver comentario original' })).toHaveAttribute('href', '#comment-1')
    })

    it('puts the quote before the author and the text of the answer', () => {
      render(<CommentList comments={[original, answer]} />)

      const when = formatDateTime('2026-10-19T13:05:00Z')
      expect(screen.getAllByRole('listitem')[1].textContent).toBe(
        `Elena Vidal${ORIGINAL}Ver comentario originalAna RojasGracias, lo reviso.${when}`,
      )
    })

    it('does not quote a comment that answers nobody', () => {
      render(<CommentList comments={[original]} />)

      expect(screen.queryByRole('blockquote')).not.toBeInTheDocument()
      expect(screen.queryByRole('link')).not.toBeInTheDocument()
    })

    it('cuts a long original at the limit and ends it with an ellipsis', () => {
      const long = ticketComment({ id: 1, author: elena, body: `${'a'.repeat(EXCERPT_LENGTH)}FIN` })

      render(<CommentList comments={[long, answer]} />)

      const quote = within(screen.getByRole('blockquote'))
      expect(quote.getByText(`${'a'.repeat(EXCERPT_LENGTH)}…`)).toBeVisible()
      expect(screen.getAllByText(/FIN/)).toHaveLength(1)
    })

    it('quotes only one level: the original shows its own text, not what it answered', () => {
      const first = ticketComment({ id: 1, body: 'Pregunta de origen' })
      const middle = ticketComment({ id: 2, author: elena, body: 'Respuesta intermedia', reply_to_id: 1 })
      const last = ticketComment({ id: 3, body: 'Respuesta final', reply_to_id: 2 })

      render(<CommentList comments={[first, middle, last]} />)

      const quote = screen.getAllByRole('blockquote')[1]
      expect(quote).toHaveTextContent('Elena VidalRespuesta intermedia')
      expect(quote).not.toHaveTextContent('Pregunta de origen')
      expect(within(screen.getAllByRole('listitem')[2]).getAllByRole('link')).toHaveLength(1)
    })

    it('says the original is not available when it is not in the list', () => {
      render(<CommentList comments={[ticketComment({ id: 2, reply_to_id: 99 })]} />)

      expect(screen.getByText('Comentario original no disponible')).toBeVisible()
      expect(screen.queryByRole('blockquote')).not.toBeInTheDocument()
      expect(screen.queryByRole('link')).not.toBeInTheDocument()
    })

    it('shows the quoted text and author as text, without interpreting them', () => {
      const markup = '<img src=x onerror="alert(1)"> <b>negrita</b>'
      const quoted = ticketComment({ id: 1, author: { id: 9, name: '<b>Eva</b>' }, body: markup })

      render(<CommentList comments={[quoted, answer]} />)

      const quote = within(screen.getByRole('blockquote'))
      expect(quote.getByText(markup)).toBeVisible()
      expect(quote.getByText('<b>Eva</b>')).toBeVisible()
      expect(document.querySelector('b, img')).toBeNull()
    })
  })
})
