import { describe, expect, it } from 'vitest'
import { EXCERPT_LENGTH, excerptOf } from './excerpt'

describe('excerptOf', () => {
  it('returns a short text as it is', () => {
    expect(excerptOf('¿Desde qué red te conectas?')).toBe('¿Desde qué red te conectas?')
  })

  it('keeps a text of exactly the limit whole, without the ellipsis', () => {
    const text = 'a'.repeat(EXCERPT_LENGTH)

    expect(excerptOf(text)).toBe(text)
  })

  it('cuts a longer text at the limit and ends it with an ellipsis', () => {
    expect(excerptOf('a'.repeat(EXCERPT_LENGTH + 1))).toBe(`${'a'.repeat(EXCERPT_LENGTH)}…`)
  })

  it('counts characters, not UTF-16 units: it never leaves half an emoji', () => {
    const cut = excerptOf('😀'.repeat(EXCERPT_LENGTH + 5))

    expect(cut).toBe(`${'😀'.repeat(EXCERPT_LENGTH)}…`)
  })

  it('does not leave spaces before the ellipsis', () => {
    expect(excerptOf(`${'a'.repeat(EXCERPT_LENGTH - 2)}   ${'b'.repeat(10)}`)).toBe(
      `${'a'.repeat(EXCERPT_LENGTH - 2)}…`,
    )
  })
})
