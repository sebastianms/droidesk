import { useParams } from 'react-router'
import { errorCode, serverMessage } from '../../api/errors'
import { ButtonLink } from '../../ui/ButtonLink'
import { ErrorNotice, LoadingNotice } from '../../ui/Notice'
import { Panel } from '../../ui/Panel'
import { homePathFor, type Role } from '../auth/access'
import { getSession } from '../auth/session'
import { DateTime } from './DateTime'
import { Fact, Facts } from './Facts'
import { PRIORITY_LABEL } from './labels'
import { useTicketDetail } from './queries'
import { SlaInfo, StatusLight } from './StatusLight'
import { TicketActions } from './TicketActions'
import styles from './TicketDetailPage.module.css'
import type { TicketDetail } from './types'

const BACK_LABEL = {
  requester: 'Volver a Mis tickets',
  agent: 'Volver a la cola',
} as const satisfies Record<Role, string>

const LOAD_FAILURE = 'Bip-bup: no pude cargar el ticket. Intenta de nuevo.'

export function TicketDetailPage() {
  const { ticketId } = useParams()
  const id = Number(ticketId)
  const ticket = useTicketDetail(id)
  const session = getSession()
  const notFound = !Number.isInteger(id) || errorCode(ticket.error) === 'not_found'

  return (
    <>
      {session && (
        <div className={styles.back}>
          <ButtonLink to={homePathFor(session.user.role)} variant="secondary">
            {BACK_LABEL[session.user.role]}
          </ButtonLink>
        </div>
      )}
      {notFound && (
        <>
          <h1>No encontrado</h1>
          <p>El ticket no existe.</p>
        </>
      )}
      {!notFound && ticket.isError && <ErrorNotice message={serverMessage(ticket.error) ?? LOAD_FAILURE} />}
      {!notFound && ticket.isPending && <LoadingNotice message="Bip-bup: cargando el ticket..." />}
      {ticket.data && <TicketView ticket={ticket.data} />}
    </>
  )
}

function TicketView({ ticket }: { ticket: TicketDetail }) {
  return (
    <>
      <header className={styles.header}>
        <p className={styles.number}>Ticket #{ticket.id}</p>
        <h1 className={styles.title}>{ticket.title}</h1>
      </header>
      <Panel title="Datos">
        <Facts>
          <Fact term="Estado">
            <StatusLight status={ticket.status} />
          </Fact>
          <Fact term="Prioridad">{PRIORITY_LABEL[ticket.priority]}</Fact>
          <Fact term="Categoría">{ticket.category.name}</Fact>
          <Fact term="Solicitante">{ticket.requester.name}</Fact>
          <Fact term="Agente">{ticket.assignee?.name ?? 'Sin asignar'}</Fact>
          <Fact term="Fecha de creación">
            <DateTime value={ticket.created_at} />
          </Fact>
          <Fact term="SLA">
            <SlaInfo sla={ticket.sla} />
          </Fact>
          {ticket.resolved_at && (
            <Fact term="Fecha de resolución">
              <DateTime value={ticket.resolved_at} />
            </Fact>
          )}
          {ticket.closed_at && (
            <Fact term="Fecha de cierre">
              <DateTime value={ticket.closed_at} />
            </Fact>
          )}
          {ticket.cancelled_at && (
            <Fact term="Fecha de cancelación">
              <DateTime value={ticket.cancelled_at} />
            </Fact>
          )}
        </Facts>
      </Panel>
      <Panel title="Descripción">
        <p className={styles.description}>{ticket.description}</p>
      </Panel>
      <TicketActions ticket={ticket} />
    </>
  )
}
