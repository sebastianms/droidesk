import { type ComponentPropsWithRef, useId } from 'react'
import { Light } from './Light'
import styles from './TextField.module.css'

interface TextFieldProps extends ComponentPropsWithRef<'input'> {
  label: string
  error?: string
}

export function TextField({ label, error, id, ...inputProps }: TextFieldProps) {
  const generatedId = useId()
  const inputId = id ?? generatedId
  const errorId = `${inputId}-error`

  return (
    <div className={styles.field}>
      <label htmlFor={inputId} className={styles.label}>
        {label}
      </label>
      <input
        {...inputProps}
        id={inputId}
        className={styles.input}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? errorId : undefined}
      />
      {error && (
        <p id={errorId}>
          <Light variant="alert" label={error} />
        </p>
      )}
    </div>
  )
}
