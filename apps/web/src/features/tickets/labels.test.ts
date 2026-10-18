import { describe, expect, it } from 'vitest'
import { ACTION_LABEL, PRIORITY_LABEL, SLA_STATE_LABEL, STATUS_LABEL } from './labels'

describe('labels', () => {
  it.each([
    ['status', STATUS_LABEL, ['open', 'in_progress', 'on_hold', 'resolved', 'closed', 'cancelled']],
    ['priority', PRIORITY_LABEL, ['critical', 'high', 'medium', 'low']],
    [
      'action',
      ACTION_LABEL,
      ['take', 'cancel', 'hold', 'resume', 'resolve', 'close', 'reopen', 'comment', 'change_priority'],
    ],
    ['SLA state', SLA_STATE_LABEL, ['on_track', 'at_risk', 'breached', 'paused', 'met', 'missed']],
  ])('has a Spanish label for every %s code of the data model', (_name, labels, codes) => {
    expect(Object.keys(labels)).toEqual(codes)
    for (const label of Object.values(labels)) expect(label).not.toBe('')
  })

  it('uses the business wording for the lifecycle', () => {
    expect(STATUS_LABEL.on_hold).toBe('En espera')
    expect(ACTION_LABEL.close).toBe('Confirmar cierre')
    expect(SLA_STATE_LABEL.at_risk).toBe('Por vencer')
  })
})
