import { describe, expect, it } from 'vitest'
import {
  COMMENT_MAX_LENGTH,
  COMMENT_REQUIRED,
  COMMENT_TOO_LONG,
  serverCommentError,
  validateComment,
} from './commentForm'

describe('validateComment', () => {
  it('accepts a comment', () => {
    expect(validateComment('¿Puedes revisar si sigue pasando?')).toBeUndefined()
  })

  it.each(['', ' ', '  \n\t '])('asks for a text when it is empty or only spaces: %j', (text) => {
    expect(validateComment(text)).toBe(COMMENT_REQUIRED)
  })

  it('accepts the limit and rejects one character more', () => {
    expect(validateComment('a'.repeat(COMMENT_MAX_LENGTH))).toBeUndefined()
    expect(validateComment('a'.repeat(COMMENT_MAX_LENGTH + 1))).toBe(COMMENT_TOO_LONG)
  })

  it('counts characters like the API, not UTF-16 units', () => {
    expect(validateComment('😀'.repeat(COMMENT_MAX_LENGTH))).toBeUndefined()
    expect(validateComment('😀'.repeat(COMMENT_MAX_LENGTH + 1))).toBe(COMMENT_TOO_LONG)
  })

  it('counts the text without the spaces around it, as the API does', () => {
    expect(validateComment(`  ${'a'.repeat(COMMENT_MAX_LENGTH)}\n`)).toBeUndefined()
  })

  it('says the limit in Spanish with the thousands separator', () => {
    expect(COMMENT_TOO_LONG).toBe(
      `El comentario admite hasta ${COMMENT_MAX_LENGTH.toLocaleString('es-CL')} caracteres.`,
    )
  })
})

describe('serverCommentError', () => {
  it('reads the message the API gives for the text', () => {
    const rejection = { detail: [{ type: 'string_too_long', loc: ['body', 'body'], msg: 'Demasiado largo' }] }

    expect(serverCommentError(rejection)).toBe('Demasiado largo')
  })

  it.each([
    ['another field of the body', ['body', 'other']],
    ['the same name outside the body', ['query', 'body']],
  ])('ignores a failure of %s', (_case, loc) => {
    expect(serverCommentError({ detail: [{ type: 'missing', loc, msg: 'Otro' }] })).toBeUndefined()
  })

  it.each([null, new Error('red'), { code: 'forbidden', message: 'No' }])(
    'is empty for a failure that is not a 422: %j',
    (error) => {
      expect(serverCommentError(error)).toBeUndefined()
    },
  )
})
