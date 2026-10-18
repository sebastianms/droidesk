import { describe, expect, it } from 'vitest'
import { serverMessage } from './errors'

describe('serverMessage', () => {
  it('returns the message of a domain error from the API', () => {
    expect(serverMessage({ code: 'not_authenticated', message: 'El usuario no existe.' })).toBe('El usuario no existe.')
  })

  it.each([
    ['a network failure', new TypeError('Failed to fetch')],
    ['a validation error', { detail: [{ loc: ['body'], msg: 'Field required', type: 'missing' }] }],
    ['an error without a message', { code: 'forbidden' }],
    ['an error without a code', { message: 'Algo pasó.' }],
    ['a message that is not text', { code: 'forbidden', message: 42 }],
    ['text', 'boom'],
    ['null', null],
    ['undefined', undefined],
  ])('returns null for %s', (_case, error) => {
    expect(serverMessage(error)).toBeNull()
  })
})
