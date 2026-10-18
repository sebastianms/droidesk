/** Las reglas de un texto obligatorio con largo máximo y los mensajes que se muestran al romperlas. */
export type TextRule = { maxLength: number; required: string; tooLong: string }

/** El mensaje de un texto que incumple su regla, o `undefined` si es válido. La API cuenta caracteres (puntos de código), no unidades UTF-16, y valida después de recortar. */
export function textError(raw: string, rule: TextRule): string | undefined {
  const length = [...raw.trim()].length
  if (length === 0) return rule.required
  return length > rule.maxLength ? rule.tooLong : undefined
}
