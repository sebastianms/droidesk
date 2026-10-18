import styles from './CommentCount.module.css'
import { commentCountLabel } from './labels'

/** Cuántos comentarios tiene un ticket, siempre en texto; sin comentarios se muestra más tenue para no competir con el título. */
export function CommentCount({ count }: { count: number }) {
  return (
    <span className={count === 0 ? styles.none : styles.some}>
      <svg className={styles.icon} width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
        <path d="M2.5 2.5h11a1 1 0 0 1 1 1v7a1 1 0 0 1-1 1h-5L5.5 14v-2.5h-3a1 1 0 0 1-1-1v-7a1 1 0 0 1 1-1z" />
      </svg>
      {commentCountLabel(count)}
    </span>
  )
}
