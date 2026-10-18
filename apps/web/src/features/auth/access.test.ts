import { describe, expect, it } from 'vitest'
import { homePathFor, isRole, ROLE_LABEL } from './access'

describe('access', () => {
  it('sends each role to its own home', () => {
    expect(homePathFor('requester')).toBe('/requester')
    expect(homePathFor('agent')).toBe('/agent')
  })

  it.each(['requester', 'agent'])('recognizes %s as a role', (role) => {
    expect(isRole(role)).toBe(true)
  })

  it.each(['admin', 'toString', '', 7, null, undefined])('rejects %j as a role', (role) => {
    expect(isRole(role)).toBe(false)
  })

  it('labels every role in Spanish', () => {
    expect(ROLE_LABEL).toEqual({ requester: 'Solicitante', agent: 'Agente' })
  })
})
