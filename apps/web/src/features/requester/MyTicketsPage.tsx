import { Link } from 'react-router'
import { $api } from '../../api/client'
import { serverMessage } from '../../api/errors'
import { ButtonLink } from '../../ui/ButtonLink'
import { EmptyState } from '../../ui/EmptyState'
import { ErrorNotice, LoadingNotice } from '../../ui/Notice'
import { DateTime } from '../tickets/DateTime'
import { Fact, Facts } from '../tickets/Facts'
import { PRIORITY_LABEL } from '../tickets/labels'
import { NEW_TICKET_PATH, ticketPath } from '../tickets/paths'
import { SlaInfo, StatusLight } from '../tickets/StatusLight'
import type { TicketSummary } from '../tickets/types'
import styles from './MyTicketsPage.module.css'

const LOAD_FAILURE = 'Bip-bup: no pude cargar tus tickets. Intenta de nuevo.'

export function MyTicketsPage() {
  const tickets = $api.useQuery('get', '/api/v1/tickets', { params: { query: { view: 'mine' } } })

  return (
    <>
      <div className={styles.header}>
        <h1>Mis tickets</h1>
        <ButtonLink to={NEW_TICKET_PATH}>Nuevo ticket</ButtonLink>
      </div>
      {tickets.isError && <ErrorNotice message={serverMessage(tickets.error) ?? LOAD_FAILURE} />}
      {tickets.isPending && <LoadingNotice message="Bip-bup: cargando tus tickets..." />}
      {tickets.data?.length === 0 && (
        <EmptyState
          title="Bip-bup: todavía no hay tickets por aquí"
          description="Cuando necesites ayuda, crea un ticket y un agente lo atenderá."
        />
      )}
      {tickets.data && tickets.data.length > 0 && (
        <ul className={styles.list}>
          {tickets.data.map((ticket) => (
            <TicketCard key={ticket.id} ticket={ticket} />
          ))}
        </ul>
      )}
    </>
  )
}

function TicketCard({ ticket }: { ticket: TicketSummary }) {
  return (
    <li className={styles.ticket}>
      <div className={styles.ticketHeader}>
        <Link to={ticketPath(ticket.id)} className={styles.title}>
          {ticket.title}
        </Link>
        <StatusLight status={ticket.status} />
      </div>
      <Facts>
        <Fact term="Categoría">{ticket.category.name}</Fact>
        <Fact term="Prioridad">{PRIORITY_LABEL[ticket.priority]}</Fact>
        <Fact term="Agente">{ticket.assignee?.name ?? 'Sin asignar'}</Fact>
        <Fact term="Creado">
          <DateTime value={ticket.created_at} />
        </Fact>
        <Fact term="SLA">
          <SlaInfo sla={ticket.sla} />
        </Fact>
      </Facts>
    </li>
  )
}
