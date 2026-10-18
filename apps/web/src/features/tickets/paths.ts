export const NEW_TICKET_PATH = '/requester/new'
export const TICKET_ROUTE = '/tickets/:ticketId'

export function ticketPath(ticketId: number): string {
  return `/tickets/${ticketId}`
}
