import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { TextField } from './TextField'

describe('TextField', () => {
  it('labels the input so it can be found by its label', () => {
    render(<TextField label="Usuario" />)

    expect(screen.getByLabelText('Usuario')).toBeInTheDocument()
  })

  it('passes the native input attributes through', async () => {
    render(<TextField label="Contraseña" type="password" autoComplete="current-password" />)

    const input = screen.getByLabelText('Contraseña')
    await userEvent.type(input, 'secreto')

    expect(input).toHaveAttribute('type', 'password')
    expect(input).toHaveAttribute('autocomplete', 'current-password')
    expect(input).toHaveValue('secreto')
  })

  it('keeps the id it is given', () => {
    render(<TextField label="Usuario" id="login-user" />)

    expect(screen.getByLabelText('Usuario')).toHaveAttribute('id', 'login-user')
  })

  it('is valid and has no description while there is no error', () => {
    render(<TextField label="Usuario" />)

    const input = screen.getByLabelText('Usuario')
    expect(input).not.toHaveAttribute('aria-invalid')
    expect(input).not.toHaveAccessibleDescription()
  })

  it('does not let the props it receives override its own error wiring', () => {
    render(<TextField label="Usuario" error="Escribe tu usuario." aria-invalid={false} aria-describedby="otro" />)

    const input = screen.getByLabelText('Usuario')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input).toHaveAccessibleDescription('Escribe tu usuario.')
  })

  it('marks the input as invalid and describes it with the error', () => {
    render(<TextField label="Usuario" error="Escribe tu usuario." />)

    const input = screen.getByLabelText('Usuario')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input).toHaveAccessibleDescription('Escribe tu usuario.')
  })
})
