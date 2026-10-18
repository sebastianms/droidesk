import { Link, type LinkProps } from 'react-router'
import styles from './Button.module.css'

interface ButtonLinkProps extends Omit<LinkProps, 'className'> {
  variant?: 'primary' | 'secondary'
}

/** Una navegación con el aspecto de un botón. */
export function ButtonLink({ variant = 'primary', ...props }: ButtonLinkProps) {
  return <Link className={`${styles.button} ${styles[variant]}`} {...props} />
}
