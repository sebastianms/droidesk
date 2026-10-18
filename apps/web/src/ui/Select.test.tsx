import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { Select } from './Select'

function renderSelect(props: { hint?: string; error?: string } = {}) {
  render(
    <Select label="Categoría" defaultValue="" {...props}>
      <option value="">Elige una categoría</option>
      <option value="1">Hardware</option>
      <option value="2">Software</option>
    </Select>,
  )
  return screen.getByRole('combobox', { name: 'Categoría' })
}

describe('Select', () => {
  it('labels the select and offers its options', () => {
    renderSelect()

    expect(screen.getAllByRole('option').map((option) => option.textContent)).toEqual([
      'Elige una categoría',
      'Hardware',
      'Software',
    ])
  })

  it('lets the user pick an option', async () => {
    const select = renderSelect()

    await userEvent.selectOptions(select, 'Software')

    expect(select).toHaveValue('2')
  })

  it('describes the select with its hint', () => {
    expect(renderSelect({ hint: 'Cómo elegir.' })).toHaveAccessibleDescription('Cómo elegir.')
  })

  it('marks the select as invalid and describes it with the error', () => {
    const select = renderSelect({ error: 'Elige una categoría.' })

    expect(select).toHaveAttribute('aria-invalid', 'true')
    expect(select).toHaveAccessibleDescription('Elige una categoría.')
  })
})
