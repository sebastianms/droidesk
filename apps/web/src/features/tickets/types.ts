import type { components } from '../../api/schema'

type Schemas = components['schemas']

export type TicketSummary = Schemas['TicketSummary']
export type TicketDetail = Schemas['TicketDetail']
export type TicketStatus = Schemas['TicketStatus']
export type TicketView = Schemas['TicketView']
export type TicketAction = Schemas['TicketAction']
export type TransitionAction = Schemas['TransitionRequest']['action']
export type Sla = Schemas['Sla']
export type SlaState = Schemas['SlaState']
export type Priority = Schemas['Priority']
export type Category = Schemas['Category']
export type SlaPolicy = Schemas['SlaPolicy']
