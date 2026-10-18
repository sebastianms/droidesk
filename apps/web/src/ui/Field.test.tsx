import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Field } from './Field'

function renderField(props: { hint?: string; error?: string; id?: string } = {}) {
  render(
    <Field label="Prioridad" {...props}>
      {(control) => <input {...control} />}
    </Field>,
  )
  return screen.getByLabelText('Prioridad')
}

describe('Field', () => {
  it('hands the control the id its label points to', () => {
    expect(renderField({ id: 'prioridad' })).toHaveAttribute('id', 'prioridad')
  })

  it('describes the control with its hint', () => {
    const control = renderField({ hint: 'Plazo: 1 día hábil.' })

    expect(control).toHaveAccessibleDescription('Plazo: 1 día hábil.')
    expect(control).not.toHaveAttribute('aria-invalid')
  })

  it('describes the control with its error, which is read first, and then with its hint', () => {
    const control = renderField({ hint: 'Plazo: 1 día hábil.', error: 'Elige una prioridad.' })

    expect(control).toHaveAttribute('aria-invalid', 'true')
    expect(control).toHaveAccessibleDescription('Elige una prioridad. Plazo: 1 día hábil.')
  })

  it('has no description when there is neither hint nor error', () => {
    expect(renderField()).not.toHaveAttribute('aria-describedby')
  })
})
