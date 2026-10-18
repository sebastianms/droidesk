import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { CommentCount } from './CommentCount'

describe('CommentCount', () => {
  it.each([
    [1, '1 comentario'],
    [3, '3 comentarios'],
  ])('says %i in words', (count, text) => {
    render(<CommentCount count={count} />)

    expect(screen.getByText(text)).toBeVisible()
  })

  it('says there are none instead of showing a bare zero', () => {
    render(<CommentCount count={0} />)

    expect(screen.getByText('Sin comentarios')).toBeVisible()
  })

  it('draws the icon as decoration, hidden from assistive technology', () => {
    const { container } = render(<CommentCount count={2} />)

    expect(container.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
  })
})
