import { describe, expect, it } from 'vitest'
import { formatDateTime } from './dates'

describe('formatDateTime', () => {
  it('writes the date and the 24-hour time in Chilean Spanish', () => {
    expect(formatDateTime('2026-10-19T13:05:00Z', 'UTC')).toBe('19 oct 2026, 13:05')
  })

  it('shows the time of the zone it is given', () => {
    expect(formatDateTime('2026-10-19T13:05:00Z', 'America/Santiago')).toBe('19 oct 2026, 10:05')
  })

  it('keeps two digits for the hour and the minutes', () => {
    expect(formatDateTime('2026-03-05T09:07:00Z', 'UTC')).toBe('5 mar 2026, 09:07')
  })

  it('uses the zone of the browser when none is given', () => {
    const browserZone = Intl.DateTimeFormat().resolvedOptions().timeZone

    expect(formatDateTime('2026-10-19T13:05:00Z')).toBe(formatDateTime('2026-10-19T13:05:00Z', browserZone))
  })
})
