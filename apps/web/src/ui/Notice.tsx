import { Light } from './Light'
import styles from './Notice.module.css'

interface NoticeProps {
  message: string
}

export function LoadingNotice({ message }: NoticeProps) {
  return (
    <p role="status" className={styles.loading}>
      {message}
    </p>
  )
}

export function ErrorNotice({ message }: NoticeProps) {
  return (
    <div role="alert">
      <Light variant="alert" label={message} />
    </div>
  )
}
