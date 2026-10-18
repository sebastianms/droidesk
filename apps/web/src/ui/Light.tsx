import styles from './Light.module.css'

export type LightVariant = 'ok' | 'warn' | 'alert' | 'holo' | 'off'

interface LightProps {
  variant: LightVariant
  label: string
}

export function Light({ variant, label }: LightProps) {
  return (
    <span className={`${styles.light} ${styles[variant]}`}>
      <span className={styles.dot} aria-hidden="true" />
      {label}
    </span>
  )
}
