import { formatDateTime } from './dates'

export function DateTime({ value }: { value: string }) {
  return <time dateTime={value}>{formatDateTime(value)}</time>
}
