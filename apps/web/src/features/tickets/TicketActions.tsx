import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { $api } from '../../api/client'
import { serverMessage } from '../../api/errors'
import { Button } from '../../ui/Button'
import { ConfirmDialog } from '../../ui/ConfirmDialog'
import { ErrorNotice } from '../../ui/Notice'
import { Panel } from '../../ui/Panel'
import { ACTION_LABEL } from './labels'
import { refreshTicketDetail, refreshTicketLists, storeTicketDetail } from './queries'
import styles from './TicketActions.module.css'
import type { TicketAction, TicketDetail, TransitionAction } from './types'

const FAILURE = 'Bip-bup: no pude aplicar el cambio. Intenta de nuevo.'

// Las acciones que cambian el estado y su énfasis. `comment` y `change_priority` no son transiciones.
const TRANSITION_VARIANT = {
  take: 'primary',
  cancel: 'secondary',
  hold: 'secondary',
  resume: 'primary',
  resolve: 'primary',
  close: 'primary',
  reopen: 'secondary',
} as const satisfies Record<TransitionAction, 'primary' | 'secondary'>

function isTransition(action: TicketAction): action is TransitionAction {
  return Object.hasOwn(TRANSITION_VARIANT, action)
}

/** Los botones salen de `allowed_actions`: la web no decide qué se puede hacer, solo lo que la API permite. */
export function TicketActions({ ticket }: { ticket: TicketDetail }) {
  const queryClient = useQueryClient()
  const [confirmingCancel, setConfirmingCancel] = useState(false)
  const transition = $api.useMutation('post', '/api/v1/tickets/{ticket_id}/transitions', {
    onSuccess: (updated) => {
      storeTicketDetail(queryClient, updated)
      return refreshTicketLists(queryClient)
    },
    // Si el cambio ya no era posible, el detalle en pantalla está desactualizado.
    onError: () => refreshTicketDetail(queryClient, ticket.id),
  })
  const actions = ticket.allowed_actions.filter(isTransition)

  // Con el fallo a la vista el panel se queda, aunque la API ya no permita ninguna acción: explica por qué.
  if (actions.length === 0 && !transition.isError) return null

  function run(action: TransitionAction) {
    transition.mutate({ params: { path: { ticket_id: ticket.id } }, body: { action } })
  }

  function confirmCancel() {
    setConfirmingCancel(false)
    run('cancel')
  }

  return (
    <Panel title="Acciones">
      <div className={styles.actions}>
        {actions.map((action) => (
          <Button
            key={action}
            variant={TRANSITION_VARIANT[action]}
            disabled={transition.isPending}
            onClick={() => (action === 'cancel' ? setConfirmingCancel(true) : run(action))}
          >
            {ACTION_LABEL[action]}
          </Button>
        ))}
      </div>
      {transition.isError && (
        <div className={styles.failure}>
          <ErrorNotice message={serverMessage(transition.error) ?? FAILURE} />
        </div>
      )}
      <ConfirmDialog
        open={confirmingCancel}
        title="Cancelar ticket"
        description="Un agente ya no podrá tomarlo y no se puede deshacer. ¿Quieres cancelarlo?"
        confirmLabel="Sí, cancelar ticket"
        dismissLabel="No, volver"
        onConfirm={confirmCancel}
        onDismiss={() => setConfirmingCancel(false)}
      />
    </Panel>
  )
}
