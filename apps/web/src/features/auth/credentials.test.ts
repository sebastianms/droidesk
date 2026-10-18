import { describe, expect, it } from 'vitest'
import {
  normalizeUsername,
  PASSWORD_MAX_LENGTH,
  PASSWORD_REQUIRED,
  USERNAME_MAX_LENGTH,
  USERNAME_REQUIRED,
  USERNAME_RULE,
  validateCredentials,
} from './credentials'

const VALID = { username: 'ana.rojas', password: 'cualquiera' }

describe('normalizeUsername', () => {
  it('trims the spaces and lowercases the name', () => {
    expect(normalizeUsername('  Ana.Rojas \t')).toBe('ana.rojas')
  })
})

describe('validateCredentials', () => {
  it('accepts a username and a password', () => {
    expect(validateCredentials(VALID)).toEqual({})
  })

  it.each(['a', 'ana.rojas', 'a_b-c.1', 'ANA', '  ana  ', 'x'.repeat(USERNAME_MAX_LENGTH)])(
    'accepts the username %j',
    (username) => {
      expect(validateCredentials({ ...VALID, username })).toEqual({})
    },
  )

  it.each(['', '   '])('asks for the username when it is %j', (username) => {
    expect(validateCredentials({ ...VALID, username })).toEqual({ username: USERNAME_REQUIRED })
  })

  it.each(['ana rojas', 'ñandú', 'ana@droidesk.local', 'ana/rojas', 'x'.repeat(USERNAME_MAX_LENGTH + 1)])(
    'explains the rule when the username is %j',
    (username) => {
      expect(validateCredentials({ ...VALID, username })).toEqual({ username: USERNAME_RULE })
    },
  )

  it('asks for the password when it is empty', () => {
    expect(validateCredentials({ ...VALID, password: '' })).toEqual({ password: PASSWORD_REQUIRED })
  })

  it.each([' ', 'x'.repeat(PASSWORD_MAX_LENGTH)])('accepts the password %j', (password) => {
    expect(validateCredentials({ ...VALID, password })).toEqual({})
  })

  it('reports both fields at once', () => {
    expect(validateCredentials({ username: '', password: '' })).toEqual({
      username: USERNAME_REQUIRED,
      password: PASSWORD_REQUIRED,
    })
  })
})
