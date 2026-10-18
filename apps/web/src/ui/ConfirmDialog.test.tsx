import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { ConfirmDialog } from './ConfirmDialog'

function renderDialog(open: boolean) {
  const onConfirm = vi.fn()
  const onDismiss = vi.fn()
  const element = (isOpen: boolean) => (
    <ConfirmDialog
      open={isOpen}
      title="Cancelar ticket"
      description="No se puede deshacer."
      confirmLabel="Sí, cancelar"
      dismissLabel="No, volver"
      onConfirm={onConfirm}
      onDismiss={onDismiss}
    />
  )
  const view = render(element(open))
  return { onConfirm, onDismiss, setOpen: (isOpen: boolean) => view.rerender(element(isOpen)) }
}

describe('ConfirmDialog', () => {
  it('stays out of the page while it is closed', () => {
    renderDialog(false)

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('opens as a modal dialog named by its title and described by its text', () => {
    renderDialog(true)

    const dialog = screen.getByRole('dialog', { name: 'Cancelar ticket' })
    expect(dialog).toHaveAccessibleDescription('No se puede deshacer.')
    expect(screen.getByRole('button', { name: 'Sí, cancelar' })).toBeVisible()
    expect(screen.getByRole('button', { name: 'No, volver' })).toBeVisible()
  })

  it('opens and closes when the open flag changes', () => {
    const { setOpen } = renderDialog(false)

    setOpen(true)
    expect(screen.getByRole('dialog')).toBeVisible()

    setOpen(false)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('confirms with the confirm button', async () => {
    const { onConfirm, onDismiss } = renderDialog(true)

    await userEvent.click(screen.getByRole('button', { name: 'Sí, cancelar' }))

    expect(onConfirm).toHaveBeenCalledOnce()
    expect(onDismiss).not.toHaveBeenCalled()
  })

  it('dismisses with the dismiss button', async () => {
    const { onConfirm, onDismiss } = renderDialog(true)

    await userEvent.click(screen.getByRole('button', { name: 'No, volver' }))

    expect(onDismiss).toHaveBeenCalledOnce()
    expect(onConfirm).not.toHaveBeenCalled()
  })

  it('dismisses with Escape, leaving the closing to its open flag', () => {
    const { onDismiss } = renderDialog(true)
    const dialog = screen.getByRole('dialog')

    const wasNotCancelled = fireEvent(dialog, new Event('cancel', { cancelable: true }))

    expect(onDismiss).toHaveBeenCalledOnce()
    expect(wasNotCancelled).toBe(false)
    expect(dialog).toBeVisible()
  })
})
