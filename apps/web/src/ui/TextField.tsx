import type { ComponentPropsWithRef } from 'react'
import { Field } from './Field'

interface TextFieldProps extends ComponentPropsWithRef<'input'> {
  label: string
  error?: string
}

export function TextField({ label, error, id, ...inputProps }: TextFieldProps) {
  return (
    <Field label={label} error={error} id={id}>
      {(control) => <input {...inputProps} {...control} />}
    </Field>
  )
}
