import { Link, useSearchParams } from 'react-router'
import { pick, withParam } from '../tickets/listFilters'
import { useTicketList } from '../tickets/queries'
import { TicketList, type TicketListMessages } from '../tickets/TicketList'
import type { TicketView } from '../tickets/types'
import styles from './QueuePage.module.css'

type AgentView = Exclude<TicketView, 'mine'>

// El orden de las pestañas; la primera es la que se ve al entrar.
const TABS = [
  { view: 'queue', label: 'Cola' },
  { view: 'assigned', label: 'Asignados a mí' },
] as const satisfies { view: AgentView; label: string }[]

const VIEWS = TABS.map((tab) => tab.view)

const MESSAGES = {
  queue: {
    loading: 'Bip-bup: cargando la cola...',
    failure: 'Bip-bup: no pude cargar la cola. Intenta de nuevo.',
    empty: {
      title: 'Bip-bup: la cola está despejada',
      description: 'No hay tickets esperando. Disfruta la calma mientras dure.',
    },
  },
  assigned: {
    loading: 'Bip-bup: cargando tus tickets asignados...',
    failure: 'Bip-bup: no pude cargar tus tickets asignados. Intenta de nuevo.',
    empty: {
      title: 'Bip-bup: no tienes tickets asignados',
      description: 'Toma uno de la cola y aparecerá aquí.',
    },
  },
} as const satisfies Record<AgentView, TicketListMessages>

/**
 * La pestaña activa vive en la URL (`?view=`), así que sobrevive a recargar y a volver desde un ticket.
 * Cambiar de pestaña conserva los filtros y el orden elegidos.
 */
export function QueuePage() {
  const [searchParams] = useSearchParams()
  const view = pick(VIEWS, searchParams.get('view')) ?? TABS[0].view
  const tickets = useTicketList(view)

  return (
    <>
      <h1>Cola de tickets</h1>
      <nav aria-label="Vistas de la cola" className={styles.tabs}>
        {TABS.map((tab) => (
          <Link
            key={tab.view}
            to={{ search: withParam(searchParams, 'view', tab.view).toString() }}
            aria-current={tab.view === view ? 'page' : undefined}
            className={styles.tab}
          >
            {tab.label}
          </Link>
        ))}
      </nav>
      <TicketList query={tickets} messages={MESSAGES[view]} showRequester />
    </>
  )
}
