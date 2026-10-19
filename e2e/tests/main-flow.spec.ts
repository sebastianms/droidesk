import { randomUUID } from 'node:crypto'
import type { Page } from '@playwright/test'
import { expect, test } from './fixtures'

const ticketData = (page: Page) => page.getByRole('region', { name: 'Datos' })
const comments = (page: Page) => page.getByRole('region', { name: 'Comentarios' })
const history = (page: Page) => page.getByRole('region', { name: 'Historial' })
const action = (page: Page, name: string) => page.getByRole('button', { name, exact: true })

async function createTicket(page: Page, title: string) {
  await page.goto('/requester/new')
  await page.getByLabel('Título').fill(title)
  await page.getByLabel('Descripción').fill('Recorrido principal del smoke end-to-end.')
  await page.getByLabel('Categoría').selectOption({ label: 'Hardware' })
  await page.getByLabel('Prioridad').selectOption({ label: 'Media' })
  await page.getByRole('button', { name: 'Crear ticket' }).click()
  await page.getByRole('link', { name: title }).click()
  await expect(page.getByRole('heading', { level: 1, name: title })).toBeVisible()
}

async function reloadAndRun(page: Page, name: string) {
  await page.reload()
  await action(page, name).click()
}

test('la solicitante y el agente llevan un ticket desde su creación hasta el cierre', async ({
  requester,
  agent,
  problems,
}) => {
  const title = `Smoke E2E ${randomUUID().slice(0, 8)}`

  await createTicket(requester, title)
  const ticketUrl = requester.url()
  await expect(ticketData(requester).getByText('Abierto', { exact: true })).toBeVisible()

  await agent.goto(ticketUrl)
  await action(agent, 'Tomar').click()
  await expect(ticketData(agent).getByText('En progreso', { exact: true })).toBeVisible()
  await expect(ticketData(agent).getByText('Elena Vidal')).toBeVisible()

  await action(agent, 'Dejar en espera').click()
  await expect(ticketData(agent).getByText('En espera', { exact: true })).toBeVisible()
  await expect(ticketData(agent).getByText('En pausa', { exact: true })).toBeVisible()

  await requester.reload()
  await expect(ticketData(requester).getByText('En pausa', { exact: true })).toBeVisible()
  await comments(requester).getByRole('textbox').fill('Ya tengo el dato que pedías.')
  await comments(requester).getByRole('button', { name: 'Comentar' }).click()
  await expect(comments(requester).getByText('Ya tengo el dato que pedías.')).toBeVisible()
  await expect(ticketData(requester).getByText('En progreso', { exact: true })).toBeVisible()
  await expect(ticketData(requester).getByText('En pausa')).toHaveCount(0)

  await reloadAndRun(agent, 'Resolver')
  await expect(ticketData(agent).getByText('Resuelto', { exact: true })).toBeVisible()

  await reloadAndRun(requester, 'Confirmar cierre')
  await expect(ticketData(requester).getByText('Cerrado', { exact: true })).toBeVisible()
  await expect(action(requester, 'Reabrir')).toHaveCount(0)

  await expect(history(requester).getByRole('listitem')).toHaveText([
    /^Ana Rojas creó el ticket/,
    /^Elena Vidal tomó el ticket/,
    /^Elena Vidal cambió el estado de Abierto a En progreso/,
    /^Elena Vidal cambió el estado de En progreso a En espera/,
    /^Ana Rojas agregó un comentario/,
    /^Ana Rojas cambió el estado de En espera a En progreso/,
    /^Elena Vidal cambió el estado de En progreso a Resuelto/,
    /^Ana Rojas cambió el estado de Resuelto a Cerrado/,
  ])

  expect(problems).toEqual([])
})
