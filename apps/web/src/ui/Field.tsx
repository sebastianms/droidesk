import { type ReactNode, useId } from 'react'
import styles from './Field.module.css'
import { Light } from './Light'

export interface FieldControlProps {
  id: string
  className: string
  'aria-invalid': true | undefined
  'aria-describedby': string | undefined
}

interface FieldProps {
  label: string
  id?: string
  hint?: string
  error?: string
  children: (control: FieldControlProps) => ReactNode
}

/** Etiqueta, ayuda y error de un control de formulario; el control recibe los atributos que lo conectan con ellos. */
export function Field({ label, id, hint, error, children }: FieldProps) {
  const generatedId = useId()
  const controlId = id ?? generatedId
  const errorId = `${controlId}-error`
  const hintId = `${controlId}-hint`
  const describedBy = [error && errorId, hint && hintId].filter(Boolean).join(' ')

  return (
    <div className={styles.field}>
      <label htmlFor={controlId} className={styles.label}>
        {label}
      </label>
      {children({
        id: controlId,
        className: styles.control,
        'aria-invalid': error ? true : undefined,
        'aria-describedby': describedBy || undefined,
      })}
      {hint && (
        <p id={hintId} className={styles.hint}>
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId}>
          <Light variant="alert" label={error} />
        </p>
      )}
    </div>
  )
}
