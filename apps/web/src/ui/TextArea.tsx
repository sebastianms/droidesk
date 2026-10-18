import type { ComponentPropsWithRef } from 'react'
import { Field } from './Field'

interface TextAreaProps extends ComponentPropsWithRef<'textarea'> {
  label: string
  error?: string
}

export function TextArea({ label, error, id, ...textAreaProps }: TextAreaProps) {
  return (
    <Field label={label} error={error} id={id}>
      {(control) => <textarea {...textAreaProps} {...control} />}
    </Field>
  )
}
