import type { ComponentPropsWithRef } from 'react'
import { Field } from './Field'

interface SelectProps extends ComponentPropsWithRef<'select'> {
  label: string
  hint?: string
  error?: string
}

export function Select({ label, hint, error, id, ...selectProps }: SelectProps) {
  return (
    <Field label={label} hint={hint} error={error} id={id}>
      {(control) => <select {...selectProps} {...control} />}
    </Field>
  )
}
