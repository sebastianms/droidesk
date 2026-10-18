import type { UseQueryResult } from '@tanstack/react-query'
import { Link } from 'react-router'
import { serverMessage } from '../../api/errors'
import { EmptyState } from '../../ui/EmptyState'
import { ErrorNotice, LoadingNotice } from '../../ui/Notice'
import { DateTime } from './DateTime'
import { Fact, Facts } from './Facts'
import { assigneeName, PRIORITY_LABEL } from './labels'
import { ticketPath } from './paths'
import { SlaInfo, StatusLight } from './StatusLight'
import styles from './TicketList.module.css'
import type { TicketSummary } from './types'

export interface TicketListMessages {
  loading: string
  failure: string
  empty: { title: string; description: string }
}

interface TicketListProps {
  query: UseQueryResult<TicketSummary[], unknown>
  messages: TicketListMessages
  /** El agente necesita saber quién pidió el ticket; el solicitante solo ve los suyos. */
  showRequester?: boolean
}

/** Los tickets de un listado en tarjetas, en el orden en que llegan, con sus estados de carga, error y vacío. */
export function TicketList({ query, messages, showRequester = false }: TicketListProps) {
  return (
    <>
      {query.isError && <ErrorNotice message={serverMessage(query.error) ?? messages.failure} />}
      {query.isPending && <LoadingNotice message={messages.loading} />}
      {query.data?.length === 0 && <EmptyState {...messages.empty} />}
      {query.data && query.data.length > 0 && (
        <ul className={styles.list}>
          {query.data.map((ticket) => (
            <TicketCard key={ticket.id} ticket={ticket} showRequester={showRequester} />
          ))}
        </ul>
      )}
    </>
  )
}

function TicketCard({ ticket, showRequester }: { ticket: TicketSummary; showRequester: boolean }) {
  return (
    <li className={styles.ticket}>
      <div className={styles.ticketHeader}>
        <Link to={ticketPath(ticket.id)} className={styles.title}>
          {ticket.title}
        </Link>
        <StatusLight status={ticket.status} />
      </div>
      <Facts>
        {showRequester && <Fact term="Solicitante">{ticket.requester.name}</Fact>}
        <Fact term="Categoría">{ticket.category.name}</Fact>
        <Fact term="Prioridad">{PRIORITY_LABEL[ticket.priority]}</Fact>
        <Fact term="Agente">{assigneeName(ticket)}</Fact>
        <Fact term="Fecha de creación">
          <DateTime value={ticket.created_at} />
        </Fact>
        <Fact term="SLA">
          <SlaInfo sla={ticket.sla} />
        </Fact>
      </Facts>
    </li>
  )
}
