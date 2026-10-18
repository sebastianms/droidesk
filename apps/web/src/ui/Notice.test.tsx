import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { ErrorNotice, LoadingNotice } from './Notice'

describe('LoadingNotice', () => {
  it('announces that something is loading', () => {
    render(<LoadingNotice message="Bip-bup: cargando..." />)

    expect(screen.getByRole('status')).toHaveTextContent('Bip-bup: cargando...')
  })
})

describe('ErrorNotice', () => {
  it('alerts with the message', () => {
    render(<ErrorNotice message="Bip-bup: algo falló." />)

    expect(screen.getByRole('alert')).toHaveTextContent('Bip-bup: algo falló.')
  })
})
