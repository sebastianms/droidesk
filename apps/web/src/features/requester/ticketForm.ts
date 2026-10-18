import { validationIssues } from '../../api/errors'

export const TITLE_MAX_LENGTH = 120
export const DESCRIPTION_MAX_LENGTH = 5000

export const TITLE_REQUIRED = 'Escribe un título.'
export const TITLE_TOO_LONG = `El título admite hasta ${TITLE_MAX_LENGTH} caracteres.`
export const DESCRIPTION_REQUIRED = 'Describe qué necesitas.'
export const DESCRIPTION_TOO_LONG = `La descripción admite hasta ${DESCRIPTION_MAX_LENGTH.toLocaleString('es-CL')} caracteres.`
export const CATEGORY_REQUIRED = 'Elige una categoría.'

export interface TicketDraft {
  title: string
  description: string
  categoryId: string
}

export interface TicketFormErrors {
  title?: string
  description?: string
  category?: string
}

export type TicketFormField = keyof TicketFormErrors

/** El orden en que aparecen los campos, para llevar el foco al primero con error. */
const FIELD_ORDER: TicketFormField[] = ['title', 'description', 'category']

// Los nombres de campo del cuerpo de `POST /api/v1/tickets`.
const SERVER_FIELDS = new Map<string, TicketFormField>([
  ['title', 'title'],
  ['description', 'description'],
  ['category_id', 'category'],
])

export function firstErrorField(errors: TicketFormErrors): TicketFormField | undefined {
  return FIELD_ORDER.find((field) => errors[field])
}

export function validateTicketDraft(draft: TicketDraft): TicketFormErrors {
  return {
    title: textError(draft.title, TITLE_MAX_LENGTH, TITLE_REQUIRED, TITLE_TOO_LONG),
    description: textError(draft.description, DESCRIPTION_MAX_LENGTH, DESCRIPTION_REQUIRED, DESCRIPTION_TOO_LONG),
    category: draft.categoryId === '' ? CATEGORY_REQUIRED : undefined,
  }
}

/** Los fallos de campo de un 422 de la API; la web valida antes de enviar, así que es una red de seguridad. */
export function serverFieldErrors(error: unknown): TicketFormErrors {
  const errors: TicketFormErrors = {}
  for (const { loc, msg } of validationIssues(error)) {
    const field = loc[0] === 'body' ? SERVER_FIELDS.get(String(loc[1])) : undefined
    if (field) errors[field] ??= msg
  }
  return errors
}

// La API cuenta caracteres (puntos de código), no unidades UTF-16, y valida después de recortar.
function textError(raw: string, maxLength: number, required: string, tooLong: string): string | undefined {
  const length = [...raw.trim()].length
  if (length === 0) return required
  return length > maxLength ? tooLong : undefined
}
