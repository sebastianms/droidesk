import { useEffect, useId, useRef } from 'react'
import { Button } from './Button'
import styles from './ConfirmDialog.module.css'

interface ConfirmDialogProps {
  open: boolean
  title: string
  description: string
  confirmLabel: string
  dismissLabel: string
  onConfirm: () => void
  onDismiss: () => void
}

/** Confirmación modal sobre `<dialog>`: el navegador atrapa el foco y lo devuelve al botón que la abrió. */
export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  dismissLabel,
  onConfirm,
  onDismiss,
}: ConfirmDialogProps) {
  const dialog = useRef<HTMLDialogElement>(null)
  const titleId = useId()
  const descriptionId = useId()

  useEffect(() => {
    const element = dialog.current
    if (!element) return
    if (open && !element.open) element.showModal()
    if (!open && element.open) element.close()
  }, [open])

  return (
    <dialog
      ref={dialog}
      className={styles.dialog}
      aria-labelledby={titleId}
      aria-describedby={descriptionId}
      onCancel={(event) => {
        // Escape: el estado `open` manda, así que el cierre nativo se cancela y lo hace el efecto.
        event.preventDefault()
        onDismiss()
      }}
    >
      <h2 id={titleId}>{title}</h2>
      <p id={descriptionId}>{description}</p>
      <div className={styles.actions}>
        <Button variant="secondary" onClick={onDismiss}>
          {dismissLabel}
        </Button>
        <Button onClick={onConfirm}>{confirmLabel}</Button>
      </div>
    </dialog>
  )
}
