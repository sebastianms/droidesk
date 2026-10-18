import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Light } from './Light'

describe('Light', () => {
  it.each(['ok', 'warn', 'alert', 'holo', 'off'] as const)('shows its text in the %s variant', (variant) => {
    render(<Light variant={variant} label="En plazo" />)

    expect(screen.getByText('En plazo')).toBeVisible()
  })
})
