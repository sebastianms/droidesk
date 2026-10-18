import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { TextArea } from './TextArea'

describe('TextArea', () => {
  it('labels the text area so it can be found by its label', () => {
    render(<TextArea label="Descripción" />)

    expect(screen.getByLabelText('Descripción').tagName).toBe('TEXTAREA')
  })

  it('passes the native attributes through and keeps what is typed, line breaks included', async () => {
    render(<TextArea label="Descripción" rows={6} />)

    const textArea = screen.getByLabelText('Descripción')
    await userEvent.type(textArea, 'Primera{Enter}Segunda')

    expect(textArea).toHaveAttribute('rows', '6')
    expect(textArea).toHaveValue('Primera\nSegunda')
  })

  it('marks the text area as invalid and describes it with the error', () => {
    render(<TextArea label="Descripción" error="Describe qué necesitas." />)

    const textArea = screen.getByLabelText('Descripción')
    expect(textArea).toHaveAttribute('aria-invalid', 'true')
    expect(textArea).toHaveAccessibleDescription('Describe qué necesitas.')
  })
})
