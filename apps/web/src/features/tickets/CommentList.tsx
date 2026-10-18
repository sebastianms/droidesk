import { Button } from '../../ui/Button'
import styles from './CommentList.module.css'
import { DateTime } from './DateTime'
import { excerptOf } from './excerpt'
import type { TicketComment } from './types'

interface CommentListProps {
  comments: TicketComment[]
  /** Solo se entrega si quien mira puede comentar: sin ella, los comentarios no ofrecen "Responder". */
  onReply?: (comment: TicketComment) => void
}

function anchorOf(commentId: number): string {
  return `comment-${commentId}`
}

/** Los comentarios del más antiguo al más reciente, como los entrega la API; el texto se muestra tal cual, nunca como HTML. */
export function CommentList({ comments, onReply }: CommentListProps) {
  if (comments.length === 0) return <p>Sin comentarios todavía.</p>

  const byId = new Map(comments.map((comment) => [comment.id, comment]))

  return (
    <ol className={styles.list}>
      {comments.map((comment) => (
        <li key={comment.id} id={anchorOf(comment.id)} className={styles.comment}>
          {comment.reply_to_id !== null && <Quote original={byId.get(comment.reply_to_id)} />}
          <p className={styles.author}>{comment.author.name}</p>
          <p className={styles.body}>{comment.body}</p>
          <span className={styles.when}>
            <DateTime value={comment.created_at} />
          </span>
          {onReply && (
            <div className={styles.actions}>
              <Button
                variant="secondary"
                aria-label={`Responder a ${comment.author.name}`}
                onClick={() => onReply(comment)}
              >
                Responder
              </Button>
            </div>
          )}
        </li>
      ))}
    </ol>
  )
}

/** La cita es de un solo nivel: muestra el cuerpo del original, sin la cita que ese a su vez tenga. */
function Quote({ original }: { original: TicketComment | undefined }) {
  if (!original) return <p className={styles.missing}>Comentario original no disponible</p>

  return (
    <div className={styles.reply}>
      <blockquote className={styles.quote}>
        <p className={styles.author}>{original.author.name}</p>
        <p className={styles.excerpt}>{excerptOf(original.body)}</p>
      </blockquote>
      <a href={`#${anchorOf(original.id)}`}>Ver comentario original</a>
    </div>
  )
}
