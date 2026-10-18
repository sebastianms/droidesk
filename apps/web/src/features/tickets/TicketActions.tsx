import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { $api } from '../../api/client'
import { serverMessage } from '../../api/errors'
import { Button } from '../../ui/Button'
import { ConfirmDialog } from '../../ui/ConfirmDialog'
import { ErrorNotice } from '../../ui/Notice'
import { Panel } from '../../ui/Panel'
import { ACTION_LABEL } from './labels'
import { PriorityControl } from './PriorityControl'
import { ticketChangeHandlers } from './queries'
import styles from './TicketActions.module.css'
import type { Priority, TicketAction, TicketDetail, TransitionAction } from './types'

const FAILURE = 'Bip-bup: no pude aplicar el cambio. Intenta de nuevo.'
const PRIORITY_FAILURE = 'Bip-bup: no pude cambiar la prioridad. Intenta de nuevo.'

// Las acciones que cambian el estado y su énfasis. `comment` y `change_priority` tienen su propio control.
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
  const handlers = ticketChangeHandlers(queryClient, ticket.id)
  const transition = $api.useMutation('post', '/api/v1/tickets/{ticket_id}/transitions', handlers)
  const priorityChange = $api.useMutation('patch', '/api/v1/tickets/{ticket_id}', handlers)
  const actions = ticket.allowed_actions.filter(isTransition)
  const canChangePriority = ticket.allowed_actions.includes('change_priority')

  // Con el fallo a la vista el panel se queda, aunque la API ya no permita ninguna acción: explica por qué.
  if (actions.length === 0 && !canChangePriority && !transition.isError && !priorityChange.isError) return null

  function run(action: TransitionAction) {
    transition.mutate({ params: { path: { ticket_id: ticket.id } }, body: { action } })
  }

  function changePriority(priority: Priority, onDone: () => void) {
    priorityChange.mutate({ params: { path: { ticket_id: ticket.id } }, body: { priority } }, { onSuccess: onDone })
  }

  function confirmCancel() {
    setConfirmingCancel(false)
    run('cancel')
  }

  return (
    <Panel title="Acciones">
      <div className={styles.body}>
        {actions.length > 0 && (
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
        )}
        {transition.isError && <ErrorNotice message={serverMessage(transition.error) ?? FAILURE} />}
        {canChangePriority && (
          <PriorityControl current={ticket.priority} pending={priorityChange.isPending} onSubmit={changePriority} />
        )}
        {priorityChange.isError && <ErrorNotice message={serverMessage(priorityChange.error) ?? PRIORITY_FAILURE} />}
      </div>
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
