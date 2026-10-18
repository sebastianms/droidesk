import { renderHook } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { useEscapeKey } from './useEscapeKey'

describe('useEscapeKey', () => {
  it('calls back when Escape is pressed while active', async () => {
    const onEscape = vi.fn()
    renderHook(() => useEscapeKey(true, onEscape))

    await userEvent.keyboard('{Escape}')

    expect(onEscape).toHaveBeenCalledOnce()
  })

  it('ignores the other keys', async () => {
    const onEscape = vi.fn()
    renderHook(() => useEscapeKey(true, onEscape))

    await userEvent.keyboard('a{Enter}')

    expect(onEscape).not.toHaveBeenCalled()
  })

  it('does nothing while inactive', async () => {
    const onEscape = vi.fn()
    renderHook(() => useEscapeKey(false, onEscape))

    await userEvent.keyboard('{Escape}')

    expect(onEscape).not.toHaveBeenCalled()
  })

  it('stops listening when it is unmounted', async () => {
    const onEscape = vi.fn()
    const { unmount } = renderHook(() => useEscapeKey(true, onEscape))
    unmount()

    await userEvent.keyboard('{Escape}')

    expect(onEscape).not.toHaveBeenCalled()
  })
})
