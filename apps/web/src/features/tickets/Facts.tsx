import type { ReactNode } from 'react'
import styles from './Facts.module.css'

/** Una lista de datos rotulados de un ticket: cada `Fact` es un par rótulo y valor. */
export function Facts({ children }: { children: ReactNode }) {
  return <dl className={styles.facts}>{children}</dl>
}

export function Fact({ term, children }: { term: string; children: ReactNode }) {
  return (
    <div>
      <dt className={styles.term}>{term}</dt>
      <dd className={styles.value}>{children}</dd>
    </div>
  )
}
