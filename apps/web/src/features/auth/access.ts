import type { components } from '../../api/schema'

export type User = components['schemas']['User']
export type DemoUser = components['schemas']['DemoUser']
export type Role = User['role']

export const LOGIN_PATH = '/login'

const HOME_PATH_BY_ROLE: Record<Role, string> = {
  requester: '/requester',
  agent: '/agent',
}

export const ROLE_LABEL = {
  requester: 'Solicitante',
  agent: 'Agente',
} as const satisfies Record<Role, string>

export function homePathFor(role: Role): string {
  return HOME_PATH_BY_ROLE[role]
}

export function isRole(value: unknown): value is Role {
  return typeof value === 'string' && Object.hasOwn(HOME_PATH_BY_ROLE, value)
}
