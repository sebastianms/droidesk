/** Fecha y hora en es-CL, 24 horas y en la zona horaria del navegador salvo que se indique otra. */
export function formatDateTime(isoDate: string, timeZone?: string): string {
  return new Intl.DateTimeFormat('es-CL', {
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
    timeZone,
  }).format(new Date(isoDate))
}
