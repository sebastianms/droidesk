import { type Browser, type Page, test as base } from '@playwright/test'

interface Fixtures {
  /** Errores de consola, de CSP y excepciones no capturadas de todas las páginas de la prueba. */
  problems: string[]
  /** Ana Rojas, solicitante, con la sesión iniciada en su propio contexto de navegador. */
  requester: Page
  /** Elena Vidal, agente, con la sesión iniciada en su propio contexto de navegador. */
  agent: Page
}

async function signIn(browser: Browser, username: string, problems: string[]): Promise<Page> {
  const page = await (await browser.newContext()).newPage()
  page.on('console', (message) => {
    if (message.type() === 'error') problems.push(`${username}: ${message.text()}`)
  })
  page.on('pageerror', (error) => problems.push(`${username}: ${error.message}`))

  await page.goto('/login')
  await page.getByLabel('Usuario', { exact: true }).fill(username)
  await page.getByLabel('Contraseña', { exact: true }).fill('cualquiera')
  await page.getByRole('button', { name: 'Ingresar' }).click()
  await page.waitForURL(/\/(requester|agent)$/)
  return page
}

export const test = base.extend<Fixtures>({
  problems: async ({}, use) => {
    await use([])
  },
  requester: async ({ browser, problems }, use) => {
    const page = await signIn(browser, 'ana.rojas', problems)
    await use(page)
    await page.context().close()
  },
  agent: async ({ browser, problems }, use) => {
    const page = await signIn(browser, 'elena.vidal', problems)
    await use(page)
    await page.context().close()
  },
})

export { expect } from '@playwright/test'
