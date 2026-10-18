import { useQueryClient } from '@tanstack/react-query'
import { type FormEvent, type RefObject, useState } from 'react'
import { flushSync } from 'react-dom'
import { $api } from '../../api/client'
import { serverMessage } from '../../api/errors'
import { Button } from '../../ui/Button'
import { ErrorNotice } from '../../ui/Notice'
import { TextArea } from '../../ui/TextArea'
import styles from './CommentBox.module.css'
import { serverCommentError, validateComment } from './commentForm'
import { excerptOf } from './excerpt'
import { refreshTicketDetail, refreshTicketLists, storeTicketDetail } from './queries'
import type { TicketComment, TicketDetail } from './types'

const FAILURE = 'Bip-bup: no pude enviar el comentario. Intenta de nuevo.'

interface CommentBoxProps {
  ticket: TicketDetail
  /** El comentario al que se responde, si se eligió uno. */
  replyTo: TicketComment | undefined
  /** El campo es de quien lo monta: también le lleva el foco cuando se elige a quién responder. */
  inputRef: RefObject<HTMLTextAreaElement | null>
  /** Avisa que ya no se responde a nadie: se publicó el comentario o se canceló la respuesta. */
  onReplyEnd: () => void
}

/** Se ofrece solo si `allowed_actions` incluye `comment`; si el ticket cambió y ya no lo permite, queda el motivo del rechazo. */
export function CommentBox({ ticket, replyTo, inputRef, onReplyEnd }: CommentBoxProps) {
  const queryClient = useQueryClient()
  const [body, setBody] = useState('')
  const [error, setError] = useState<string>()
  const comment = $api.useMutation('post', '/api/v1/tickets/{ticket_id}/comments', {
    onSuccess: (updated) => {
      // Primero y de forma síncrona: el campo debe estar vacío antes de que el detalle muestre el comentario nuevo.
      flushSync(() => {
        setBody('')
        onReplyEnd()
      })
      // El comentario del solicitante puede haber reanudado el ticket: el estado cambia en el detalle y en los listados.
      storeTicketDetail(queryClient, updated)
      // Sin esperarlo: los listados se actualizan en segundo plano y el formulario queda libre de inmediato.
      refreshTicketLists(queryClient)
    },
    onError: async (rejection) => {
      const fieldError = serverCommentError(rejection)
      if (fieldError) {
        showError(fieldError)
      } else {
        // Un fallo que no es del campo suele ser un estado que cambió: la pantalla está desactualizada.
        await Promise.all([refreshTicketDetail(queryClient, ticket.id), refreshTicketLists(queryClient)])
      }
    },
  })

  function showError(message: string | undefined) {
    // Síncrono: el campo ya debe estar descrito por su error cuando recibe el foco, para que se anuncie.
    flushSync(() => setError(message))
    if (message) inputRef.current?.focus()
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const found = validateComment(body)
    showError(found)
    if (found) return
    comment.mutate({
      params: { path: { ticket_id: ticket.id } },
      body: { body: body.trim(), reply_to_id: replyTo?.id },
    })
  }

  function cancelReply() {
    onReplyEnd()
    inputRef.current?.focus()
  }

  const notice = comment.isError && !error && <ErrorNotice message={serverMessage(comment.error) ?? FAILURE} />

  if (!ticket.allowed_actions.includes('comment')) return notice || null

  return (
    <form className={styles.form} onSubmit={submit} noValidate>
      {replyTo && (
        <div className={styles.replying}>
          <p role="status">{`Respondiendo a ${replyTo.author.name}: «${excerptOf(replyTo.body)}»`}</p>
          <Button variant="secondary" onClick={cancelReply}>
            Cancelar respuesta
          </Button>
        </div>
      )}
      <TextArea
        ref={inputRef}
        label="Agregar un comentario"
        rows={4}
        value={body}
        error={error}
        onChange={(event) => {
          setBody(event.target.value)
          setError(undefined)
          comment.reset()
        }}
      />
      {notice}
      <div className={styles.actions}>
        <Button type="submit" disabled={comment.isPending}>
          {comment.isPending ? 'Comentando...' : 'Comentar'}
        </Button>
      </div>
    </form>
  )
}
