import { DroidLogo } from './DroidLogo'
import styles from './EmptyState.module.css'
import { Panel } from './Panel'

interface EmptyStateProps {
  title: string
  description: string
}

export function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <Panel>
      <div className={styles.empty}>
        <DroidLogo size={72} />
        <p className={styles.title}>{title}</p>
        <p className={styles.description}>{description}</p>
      </div>
    </Panel>
  )
}
