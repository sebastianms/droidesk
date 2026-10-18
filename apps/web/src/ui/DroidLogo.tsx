import styles from './DroidLogo.module.css'

interface DroidLogoProps {
  size?: number
}

/** Droide astromecánico estilizado: dibujo propio, sin material de terceros. */
export function DroidLogo({ size = 40 }: DroidLogoProps) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" aria-hidden="true" focusable="false">
      <rect className={styles.accent} x="9" y="28" width="7" height="25" rx="2" />
      <rect className={styles.accent} x="48" y="28" width="7" height="25" rx="2" />
      <rect className={styles.accent} x="6" y="51" width="13" height="6" rx="2" />
      <rect className={styles.accent} x="45" y="51" width="13" height="6" rx="2" />
      <rect className={styles.hull} x="16" y="24" width="32" height="30" rx="3" />
      <rect className={styles.accent} x="20" y="33" width="24" height="6" rx="1.5" />
      <rect className={styles.accent} x="20" y="43" width="10" height="6" rx="1.5" />
      <circle className={styles.holo} cx="38" cy="46" r="2.5" />
      <path className={styles.hull} d="M16 24a16 16 0 0 1 32 0z" />
      <path className={styles.accent} d="M16.6 21.5a16 16 0 0 1 30.8 0z" />
      <circle className={styles.lens} cx="32" cy="15" r="6" />
      <circle className={styles.holo} cx="32" cy="15" r="3.5" />
    </svg>
  )
}
