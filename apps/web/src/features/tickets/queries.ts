import type { QueryClient } from '@tanstack/react-query'
import { $api } from '../../api/client'
import type { TicketDetail, TicketView } from './types'

const LIST_PATH = '/api/v1/tickets'
const DETAIL_PATH = '/api/v1/tickets/{ticket_id}'

function detailInit(ticketId: number) {
  return { params: { path: { ticket_id: ticketId } } }
}

/** Un listado de tickets: `mine` para el solicitante, `queue` y `assigned` para el agente. */
export function useTicketList(view: TicketView) {
  return $api.useQuery('get', LIST_PATH, { params: { query: { view } } })
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
  const listKey = $api.queryOptions('get', LIST_PATH).queryKey
  return queryClient.invalidateQueries({ queryKey: listKey, refetchType: 'all' })
}

/** Qué hacer al terminar un cambio al ticket: con éxito, guardar su detalle y actualizar los listados; si la API lo rechaza, la pantalla está desactualizada y se vuelve a pedir todo. */
export function ticketChangeHandlers(queryClient: QueryClient, ticketId: number) {
  return {
    onSuccess: (updated: TicketDetail) => {
      storeTicketDetail(queryClient, updated)
      return refreshTicketLists(queryClient)
    },
    onError: () => Promise.all([refreshTicketDetail(queryClient, ticketId), refreshTicketLists(queryClient)]),
  }
}
