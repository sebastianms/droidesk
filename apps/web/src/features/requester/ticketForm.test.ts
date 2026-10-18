import { describe, expect, it } from 'vitest'
import {
  CATEGORY_REQUIRED,
  DESCRIPTION_MAX_LENGTH,
  DESCRIPTION_REQUIRED,
  DESCRIPTION_TOO_LONG,
  firstErrorField,
  serverFieldErrors,
  TITLE_MAX_LENGTH,
  TITLE_REQUIRED,
  TITLE_TOO_LONG,
  validateTicketDraft,
} from './ticketForm'

const valid = { title: 'No enciende el monitor', description: 'Pantalla negra', categoryId: '1' }

describe('validateTicketDraft', () => {
  it('accepts a complete ticket', () => {
    expect(firstErrorField(validateTicketDraft(valid))).toBeUndefined()
  })

  it('asks for every missing field at once', () => {
    expect(validateTicketDraft({ title: '', description: '', categoryId: '' })).toEqual({
      title: TITLE_REQUIRED,
      description: DESCRIPTION_REQUIRED,
      category: CATEGORY_REQUIRED,
    })
  })

  it.each([
    ['title', TITLE_REQUIRED],
    ['description', DESCRIPTION_REQUIRED],
  ])('treats a %s of only spaces as empty', (field, message) => {
    expect(validateTicketDraft({ ...valid, [field]: '  \n\t ' })).toMatchObject({ [field]: message })
  })

  it.each([
    ['title', TITLE_MAX_LENGTH, TITLE_TOO_LONG],
    ['description', DESCRIPTION_MAX_LENGTH, DESCRIPTION_TOO_LONG],
  ])('accepts a %s at its limit and rejects one character more', (field, limit, message) => {
    expect(validateTicketDraft({ ...valid, [field]: 'a'.repeat(limit) })).toMatchObject({ [field]: undefined })
    expect(validateTicketDraft({ ...valid, [field]: 'a'.repeat(limit + 1) })).toMatchObject({ [field]: message })
  })

  it('counts the limit after trimming, like the API', () => {
    expect(validateTicketDraft({ ...valid, title: `  ${'a'.repeat(TITLE_MAX_LENGTH)}  ` }).title).toBeUndefined()
  })

  it('counts characters, not UTF-16 units, like the API', () => {
    expect(validateTicketDraft({ ...valid, title: '😀'.repeat(TITLE_MAX_LENGTH) }).title).toBeUndefined()
    expect(validateTicketDraft({ ...valid, title: '😀'.repeat(TITLE_MAX_LENGTH + 1) }).title).toBe(TITLE_TOO_LONG)
  })

  it('writes the description limit with the Chilean thousands separator', () => {
    expect(DESCRIPTION_TOO_LONG).toBe('La descripción admite hasta 5.000 caracteres.')
  })
})

describe('firstErrorField', () => {
  it('follows the order of the form', () => {
    expect(firstErrorField({ category: 'x', description: 'y' })).toBe('description')
    expect(firstErrorField({ category: 'x', title: 'z', description: 'y' })).toBe('title')
    expect(firstErrorField({ category: 'x' })).toBe('category')
  })

  it('finds nothing when there are no errors', () => {
    expect(firstErrorField({})).toBeUndefined()
    expect(firstErrorField({ title: undefined })).toBeUndefined()
  })
})

describe('serverFieldErrors', () => {
  it('maps the fields of the body to the fields of the form', () => {
    const error = {
      detail: [
        { loc: ['body', 'category_id'], msg: 'La categoría no existe.', type: 'value_error' },
        { loc: ['body', 'title'], msg: 'Field required', type: 'missing' },
      ],
    }

    expect(serverFieldErrors(error)).toEqual({ category: 'La categoría no existe.', title: 'Field required' })
  })

  it('keeps the first message of a field', () => {
    const error = {
      detail: [
        { loc: ['body', 'title'], msg: 'primero', type: 'x' },
        { loc: ['body', 'title'], msg: 'segundo', type: 'x' },
      ],
    }

    expect(serverFieldErrors(error)).toEqual({ title: 'primero' })
  })

  it.each([
    ['a field the form does not have', { detail: [{ loc: ['body', 'priority'], msg: 'x', type: 'x' }] }],
    ['an inherited name', { detail: [{ loc: ['body', 'constructor'], msg: 'x', type: 'x' }] }],
    ['a field outside the body', { detail: [{ loc: ['query', 'title'], msg: 'x', type: 'x' }] }],
    ['a domain error', { code: 'forbidden', message: 'No puedes.' }],
    ['a network failure', new TypeError('Failed to fetch')],
  ])('ignores %s', (_case, error) => {
    expect(serverFieldErrors(error)).toEqual({})
  })
})
