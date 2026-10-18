import { describe, expect, it } from 'vitest'
import { errorCode, serverMessage, validationIssues } from './errors'

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

describe('errorCode', () => {
  it('returns the code of a domain error from the API', () => {
    expect(errorCode({ code: 'not_found', message: 'El ticket no existe.' })).toBe('not_found')
  })

  it.each([
    ['a network failure', new TypeError('Failed to fetch')],
    ['a validation error', { detail: [] }],
    ['an error without a message', { code: 'not_found' }],
    ['null', null],
  ])('returns null for %s', (_case, error) => {
    expect(errorCode(error)).toBeNull()
  })
})

describe('validationIssues', () => {
  it('returns the issues of a validation error', () => {
    const issue = { loc: ['body', 'title'], msg: 'Field required', type: 'missing' }

    expect(validationIssues({ detail: [issue] })).toEqual([issue])
  })

  it('drops the entries that are not issues', () => {
    const issue = { loc: ['body', 'title'], msg: 'Field required', type: 'missing' }

    expect(
      validationIssues({ detail: [issue, 'boom', { loc: 'body', msg: 'x' }, { loc: [], msg: 42 }, null] }),
    ).toEqual([issue])
  })

  it.each([
    ['a domain error', { code: 'forbidden', message: 'No puedes.' }],
    ['a detail that is not a list', { detail: 'Not found' }],
    ['a network failure', new TypeError('Failed to fetch')],
    ['text', 'boom'],
    ['null', null],
    ['undefined', undefined],
  ])('returns nothing for %s', (_case, error) => {
    expect(validationIssues(error)).toEqual([])
  })
})
