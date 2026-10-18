import type { UseQueryResult } from '@tanstack/react-query'
import { Link } from 'react-router'
import { serverMessage } from '../../api/errors'
import { EmptyState } from '../../ui/EmptyState'
import { ErrorNotice, LoadingNotice } from '../../ui/Notice'
import { CommentCount } from './CommentCount'
import { DateTime } from './DateTime'
import { Fact, Facts } from './Facts'
import { ListControls } from './ListControls'
import { assigneeName, PRIORITY_LABEL } from './labels'
import { applyListFilters } from './listFilters'
import { ticketPath } from './paths'
import { SlaLight } from './SlaLight'
import { StatusLight } from './StatusLight'
import styles from './TicketList.module.css'
import type { TicketSummary } from './types'
import { useListFilters } from './useListFilters'

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

const NO_MATCH = {
  title: 'Bip-bup: ningún ticket coincide con los filtros',
  description: 'Prueba con otra prioridad o estado de SLA, o limpia los filtros para ver todos los tickets.',
}

/** Los tickets de un listado en tarjetas, con sus estados de carga, error y vacío. Se pueden filtrar y ordenar; sin orden elegido salen como llegan. */
export function TicketList({ query, messages, showRequester = false }: TicketListProps) {
  return (
    <>
      {query.isError && <ErrorNotice message={serverMessage(query.error) ?? messages.failure} />}
      {query.isPending && <LoadingNotice message={messages.loading} />}
      {query.data?.length === 0 && <EmptyState {...messages.empty} />}
      {query.data && query.data.length > 0 && <FilterableTickets tickets={query.data} showRequester={showRequester} />}
    </>
  )
}

function FilterableTickets({ tickets, showRequester }: { tickets: TicketSummary[]; showRequester: boolean }) {
  const { filters, setFilter, clear } = useListFilters()
  const visible = applyListFilters(tickets, filters)

  return (
    <>
      <ListControls
        filters={filters}
        shown={visible.length}
        total={tickets.length}
        onChange={setFilter}
        onClear={clear}
      />
      {visible.length === 0 && <EmptyState {...NO_MATCH} />}
      {visible.length > 0 && (
        <ul className={styles.list}>
          {visible.map((ticket) => (
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
        <div className={styles.heading}>
          <Link to={ticketPath(ticket.id)} className={styles.title}>
            {ticket.title}
          </Link>
          <CommentCount count={ticket.comment_count} />
        </div>
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
          <SlaLight sla={ticket.sla} />
        </Fact>
      </Facts>
    </li>
  )
}
