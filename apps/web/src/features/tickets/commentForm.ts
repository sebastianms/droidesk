import { validationIssues } from '../../api/errors'
import { type TextRule, textError } from './textError'

export const COMMENT_MAX_LENGTH = 2000

export const COMMENT_REQUIRED = 'Escribe un comentario.'
export const COMMENT_TOO_LONG = `El comentario admite hasta ${COMMENT_MAX_LENGTH.toLocaleString('es-CL')} caracteres.`

const COMMENT_RULE: TextRule = { maxLength: COMMENT_MAX_LENGTH, required: COMMENT_REQUIRED, tooLong: COMMENT_TOO_LONG }

// En un 422, `loc` empieza por la parte de la request (el cuerpo) y sigue con el campo (el texto del comentario).
const REQUEST_PART = 'body'
const COMMENT_TEXT_FIELD = 'body'

export function validateComment(body: string): string | undefined {
  return textError(body, COMMENT_RULE)
}

/** El fallo del texto en un 422 de la API; la web valida antes de enviar, así que es una red de seguridad. */
export function serverCommentError(error: unknown): string | undefined {
  return validationIssues(error).find(({ loc: [part, field] }) => part === REQUEST_PART && field === COMMENT_TEXT_FIELD)
    ?.msg
}
