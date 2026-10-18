import { describe, expect, it } from 'vitest'
import { slaPolicies } from '../../test/fixtures'
import {
  ACTION_LABEL,
  assigneeName,
  commentCountLabel,
  PRIORITY_LABEL,
  policyLabel,
  SLA_STATE_LABEL,
  SORT_LABEL,
  STATUS_LABEL,
  shownCountLabel,
} from './labels'

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
    ['sort order', SORT_LABEL, ['due', 'priority', 'recent']],
  ])('has a Spanish label for every %s code of the data model', (_name, labels, codes) => {
    expect(Object.keys(labels)).toEqual(codes)
    for (const label of Object.values(labels)) expect(label).not.toBe('')
  })

  it('uses the business wording for the lifecycle', () => {
    expect(STATUS_LABEL.on_hold).toBe('En espera')
    expect(ACTION_LABEL.close).toBe('Confirmar cierre')
    expect(SLA_STATE_LABEL.at_risk).toBe('Por vencer')
  })

  describe('assigneeName', () => {
    it('is the name of the agent who has the ticket', () => {
      expect(assigneeName({ assignee: { id: 5, name: 'Elena Vidal' } })).toBe('Elena Vidal')
    })

    it('says "Sin asignar" while nobody has taken the ticket', () => {
      expect(assigneeName({ assignee: null })).toBe('Sin asignar')
    })
  })

  describe('commentCountLabel', () => {
    it.each([
      [0, 'Sin comentarios'],
      [1, '1 comentario'],
      [2, '2 comentarios'],
      [12, '12 comentarios'],
    ])('says %i as "%s"', (count, label) => {
      expect(commentCountLabel(count)).toBe(label)
    })
  })

  describe('shownCountLabel', () => {
    it.each([
      [2, 5, 'Mostrando 2 de 5 tickets'],
      [0, 3, 'Mostrando 0 de 3 tickets'],
      [1, 1, 'Mostrando 1 de 1 ticket'],
      [1, 4, 'Mostrando 1 de 4 tickets'],
    ])('says %i of %i as "%s"', (shown, total, label) => {
      expect(shownCountLabel(shown, total)).toBe(label)
    })
  })

  describe('policyLabel', () => {
    it.each([
      [0, 'Crítica · 4 horas hábiles'],
      [1, 'Alta · 1 día hábil'],
      [2, 'Media · 3 días hábiles'],
      [3, 'Baja · 5 días hábiles'],
    ])('says the priority and its deadline for the policy %i', (index, label) => {
      expect(policyLabel(slaPolicies[index])).toBe(label)
    })

    it('uses the singular only for exactly one unit', () => {
      expect(policyLabel({ ...slaPolicies[0], target_amount: 1 })).toBe('Crítica · 1 hora hábil')
    })
  })
})
