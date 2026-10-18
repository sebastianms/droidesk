import type { components } from './schema'

type ErrorBody = components['schemas']['ErrorBody']
type ValidationIssue = components['schemas']['ValidationError']

/** El mensaje de un error de dominio de la API; `null` si el fallo fue otro (red, validación, 500). */
export function serverMessage(error: unknown): string | null {
  return isErrorBody(error) ? error.message : null
}

/** El código de un error de dominio de la API; `null` si el fallo fue otro (red, validación, 500). */
export function errorCode(error: unknown): ErrorBody['code'] | null {
  return isErrorBody(error) ? error.code : null
}

/** Los fallos por campo de un 422; vacío si el error no es de validación. */
export function validationIssues(error: unknown): ValidationIssue[] {
  if (typeof error !== 'object' || error === null || !('detail' in error) || !Array.isArray(error.detail)) return []
  return error.detail.filter(isValidationIssue)
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

function isValidationIssue(value: unknown): value is ValidationIssue {
  return (
    typeof value === 'object' &&
    value !== null &&
    'loc' in value &&
    Array.isArray(value.loc) &&
    'msg' in value &&
    typeof value.msg === 'string'
  )
}
