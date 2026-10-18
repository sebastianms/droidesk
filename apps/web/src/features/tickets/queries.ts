import type { QueryClient } from '@tanstack/react-query'
import { $api } from '../../api/client'
import type { TicketDetail } from './types'

const DETAIL_PATH = '/api/v1/tickets/{ticket_id}'

function detailInit(ticketId: number) {
  return { params: { path: { ticket_id: ticketId } } }
}

export function useTicketDetail(ticketId: number) {
  return $api.useQuery('get', DETAIL_PATH, detailInit(ticketId), { enabled: Number.isInteger(ticketId) })
}

function detailKey(ticketId: number) {
  return $api.queryOptions('get', DETAIL_PATH, detailInit(ticketId)).queryKey
}

/** Reemplaza el detalle en caché por la respuesta más reciente de la API, sin volver a pedirlo. */
export function storeTicketDetail(queryClient: QueryClient, ticket: TicketDetail): void {
  queryClient.setQueryData(detailKey(ticket.id), ticket)
}

export function refreshTicketDetail(queryClient: QueryClient, ticketId: number): Promise<void> {
  return queryClient.invalidateQueries({ queryKey: detailKey(ticketId) })
}

/** Vuelve a pedir todos los listados, incluso los que no están en pantalla, para que lleguen al día cuando se abran. */
export function refreshTicketLists(queryClient: QueryClient): Promise<void> {
  const listKey = $api.queryOptions('get', '/api/v1/tickets').queryKey
  return queryClient.invalidateQueries({ queryKey: listKey, refetchType: 'all' })
}
