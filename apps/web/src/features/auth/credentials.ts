export const USERNAME_MAX_LENGTH = 50
export const PASSWORD_MAX_LENGTH = 128

// Debe coincidir con el patrón de `LoginRequest.username` en la API.
const USERNAME_PATTERN = new RegExp(`^[a-z0-9._-]{1,${USERNAME_MAX_LENGTH}}$`)

export const USERNAME_REQUIRED = 'Escribe tu usuario.'
export const USERNAME_RULE = `Usa letras sin tilde, números, punto, guion o guion bajo, hasta ${USERNAME_MAX_LENGTH} caracteres.`
export const PASSWORD_REQUIRED = 'Escribe tu contraseña.'

export interface CredentialErrors {
  username?: string
  password?: string
}

export function normalizeUsername(raw: string): string {
  return raw.trim().toLowerCase()
}

export function validateCredentials(input: { username: string; password: string }): CredentialErrors {
  return { ...validateUsername(input.username), ...validatePassword(input.password) }
}

function validateUsername(raw: string): CredentialErrors {
  const username = normalizeUsername(raw)
  if (username === '') return { username: USERNAME_REQUIRED }
  if (!USERNAME_PATTERN.test(username)) return { username: USERNAME_RULE }
  return {}
}

function validatePassword(password: string): CredentialErrors {
  return password === '' ? { password: PASSWORD_REQUIRED } : {}
}
