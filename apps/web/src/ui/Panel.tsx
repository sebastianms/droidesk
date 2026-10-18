import { type ReactNode, useId } from 'react'
import styles from './Panel.module.css'

interface PanelProps {
  title?: string
  action?: ReactNode
  children: ReactNode
}

export function Panel({ title, action, children }: PanelProps) {
  const titleId = useId()

  return (
    <section className={styles.panel} aria-labelledby={title ? titleId : undefined}>
      {title && (
        <div className={styles.header}>
          <h2 id={titleId}>{title}</h2>
          {action}
        </div>
      )}
      {children}
    </section>
  )
}
