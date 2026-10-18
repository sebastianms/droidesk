import { EmptyState } from '../../ui/EmptyState'

export function MyTicketsPage() {
  return (
    <>
      <h1>Mis tickets</h1>
      <EmptyState
        title="Bip-bup: todavía no hay tickets por aquí"
        description="Cuando necesites ayuda, crea un ticket y un agente lo atenderá."
      />
    </>
  )
}
