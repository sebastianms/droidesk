import type { ComponentPropsWithRef } from 'react'
import styles from './IconButton.module.css'

interface IconButtonProps extends Omit<ComponentPropsWithRef<'button'>, 'aria-label'> {
  label: string
}

export function IconButton({ label, type = 'button', className, children, ...props }: IconButtonProps) {
  const classes = [styles.button, className].filter(Boolean).join(' ')

  return (
    <button type={type} aria-label={label} className={classes} {...props}>
      <span aria-hidden="true">{children}</span>
    </button>
  )
}
