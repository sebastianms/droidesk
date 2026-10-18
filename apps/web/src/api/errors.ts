import type { components } from './schema'

type ErrorBody = components['schemas']['ErrorBody']

/** El mensaje de un error de dominio de la API; `null` si el fallo fue otro (red, validación, 500). */
export function serverMessage(error: unknown): string | null {
  return isErrorBody(error) ? error.message : null
}

function isErrorBody(value: unknown): value is ErrorBody {
  return (
    typeof value === 'object' &&
    value !== null &&
    'code' in value &&
    typeof value.code === 'string' &&
    'message' in value &&
    typeof value.message === 'string'
  )
}
