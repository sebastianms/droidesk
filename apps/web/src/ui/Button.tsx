import type { ComponentPropsWithoutRef } from 'react'
import styles from './Button.module.css'

interface ButtonProps extends ComponentPropsWithoutRef<'button'> {
  variant?: 'primary' | 'secondary'
}

export function Button({ variant = 'primary', type = 'button', className, ...props }: ButtonProps) {
  const classes = [styles.button, styles[variant], className].filter(Boolean).join(' ')

  return <button type={type} className={classes} {...props} />
}
