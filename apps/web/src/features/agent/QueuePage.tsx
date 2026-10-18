import { EmptyState } from '../../ui/EmptyState'

export function QueuePage() {
  return (
    <>
      <h1>Cola de tickets</h1>
      <EmptyState
        title="Bip-bup: la cola está despejada"
        description="No hay tickets esperando. Disfruta la calma mientras dure."
      />
    </>
  )
}
