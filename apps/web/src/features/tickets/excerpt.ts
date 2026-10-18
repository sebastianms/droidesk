export const EXCERPT_LENGTH = 120

/** El comienzo de un comentario para citarlo; corta por caracteres (puntos de código), no por unidades UTF-16, y avisa con «…» que hay más. */
export function excerptOf(body: string): string {
  const characters = [...body]
  if (characters.length <= EXCERPT_LENGTH) return body
  return `${characters.slice(0, EXCERPT_LENGTH).join('').trimEnd()}…`
}
