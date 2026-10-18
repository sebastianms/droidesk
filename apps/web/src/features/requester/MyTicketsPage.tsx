import { ButtonLink } from '../../ui/ButtonLink'
import { NEW_TICKET_PATH } from '../tickets/paths'
import { useTicketList } from '../tickets/queries'
import { TicketList, type TicketListMessages } from '../tickets/TicketList'
import styles from './MyTicketsPage.module.css'

const MESSAGES = {
  loading: 'Bip-bup: cargando tus tickets...',
  failure: 'Bip-bup: no pude cargar tus tickets. Intenta de nuevo.',
  empty: {
    title: 'Bip-bup: todavía no hay tickets por aquí',
    description: 'Cuando necesites ayuda, crea un ticket y un agente lo atenderá.',
  },
} as const satisfies TicketListMessages

export function MyTicketsPage() {
  const tickets = useTicketList('mine')

  return (
    <>
      <div className={styles.header}>
        <h1>Mis tickets</h1>
        <ButtonLink to={NEW_TICKET_PATH}>Nuevo ticket</ButtonLink>
      </div>
      <TicketList query={tickets} messages={MESSAGES} />
    </>
  )
}
