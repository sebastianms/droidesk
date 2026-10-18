import { useRef, useState } from 'react'
import { CommentBox } from './CommentBox'
import { CommentList } from './CommentList'
import styles from './Conversation.module.css'
import type { TicketComment, TicketDetail } from './types'

/** Los comentarios y el campo para escribir; aquí vive a quién se responde, porque se elige en la lista y se muestra en el campo. */
export function Conversation({ ticket }: { ticket: TicketDetail }) {
  const input = useRef<HTMLTextAreaElement>(null)
  const [replyToId, setReplyToId] = useState<number>()
  const replyTo = ticket.comments.find((comment) => comment.id === replyToId)
  const canComment = ticket.allowed_actions.includes('comment')

  function reply(comment: TicketComment) {
    setReplyToId(comment.id)
    input.current?.focus()
  }

  return (
    <div className={styles.conversation}>
      <CommentList comments={ticket.comments} onReply={canComment ? reply : undefined} />
      <CommentBox ticket={ticket} replyTo={replyTo} inputRef={input} onReplyEnd={() => setReplyToId(undefined)} />
    </div>
  )
}
