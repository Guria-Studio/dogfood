import { expect, test } from '@playwright/test'

// El flujo nuevo de F11 sobre el `runs/` de prueba (e2e/preparar_runs.py). Las capturas en tema claro
// de cada página principal van a docs/capturas/f11/ (se regeneran en cada corrida).
const CAPTURAS = '../docs/capturas/f11'
const foto = (page: import('@playwright/test').Page, nombre: string) =>
  page.screenshot({ path: `${CAPTURAS}/${nombre}.png`, fullPage: true })

test.beforeEach(async ({ context }) => {
  await context.grantPermissions(['clipboard-read', 'clipboard-write'])
})

test('inicio → proyectos → proyecto nuevo (3 pasos) → casos de prueba', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Inicio', level: 1 })).toBeVisible()
  await foto(page, 'inicio')

  await page.getByRole('link', { name: 'Proyectos', exact: true }).first().click()
  await expect(page.getByRole('heading', { name: 'Proyectos', level: 1 })).toBeVisible()
  await expect(page.locator('[data-proyecto="predicts"]')).toBeVisible()
  await foto(page, 'proyectos')

  await page.getByRole('link', { name: 'Proyecto nuevo' }).click()
  await expect(page.getByRole('heading', { name: 'Proyecto nuevo', level: 1 })).toBeVisible()
  // ponytail: hasta F13 el alta exige un `objetivo` conocido (android/ios/flutter_web/predicts) y el
  // asistente usa el slug como objetivo; «Android» es el único nombre que hoy lo cumple.
  await page.getByLabel('Android').check()
  await page.getByLabel(/Objetivo/).fill('com.ejemplo.app')
  await page.getByLabel('Nombre').fill('Android')
  await foto(page, 'proyecto-nuevo')
  await page.getByRole('button', { name: 'Siguiente' }).click()
  await page.getByLabel('Sin login').check()
  await page.getByRole('button', { name: 'Siguiente' }).click()
  await page.getByLabel('Instrucciones extra').fill('Enfócate en el registro')
  await page.getByRole('button', { name: 'Crear proyecto' }).click()

  await expect(page).toHaveURL(/\/proyectos\/android\/casos/)
  await expect(page.getByRole('heading', { name: 'Casos de prueba', level: 1 })).toBeVisible()
  await expect(page.getByText('Genera el plan')).toBeVisible()
})

test('casos: filtrar fallidos → sheet → Error, Causa y Arreglo → copiar el prompt', async ({ page }) => {
  await page.goto('/proyectos/predicts/casos')
  await expect(page.getByRole('heading', { name: 'Casos de prueba', level: 1 })).toBeVisible()
  await expect(page.locator('[data-caso]')).toHaveCount(3)
  await foto(page, 'casos')

  await page.getByRole('tab', { name: /Fallaron/ }).click()
  await expect(page).toHaveURL(/estado=fallo/)
  await expect(page.locator('[data-caso]')).toHaveCount(2)

  await page.locator('[data-caso="TC002"]').click()
  await expect(page).toHaveURL(/caso=TC002/)
  const sheet = page.getByRole('dialog')
  await expect(sheet.getByRole('heading', { name: 'Bob hace login-fallido' })).toBeVisible()
  await foto(page, 'casos-sheet')

  const diag = sheet.getByRole('tablist', { name: 'Diagnóstico' })
  await expect(sheet.getByRole('tabpanel', { name: 'Error' })).toContainText('pantalla en blanco')
  await diag.getByRole('tab', { name: 'Causa' }).click()
  await expect(sheet.getByText('El formulario ignora el 500 del servidor')).toBeVisible()
  await diag.getByRole('tab', { name: 'Arreglo' }).click()
  await expect(sheet.getByText('Mostrar el mensaje de error')).toBeVisible()
  await expect(sheet.getByText('app/login.tsx:42')).toBeVisible()

  await sheet.getByRole('button', { name: 'Copiar prompt de arreglo' }).click()
  await expect(page.getByText('Prompt de arreglo copiado')).toBeVisible()
  const portapapeles = await page.evaluate(() => navigator.clipboard.readText())
  expect(portapapeles).toContain('TC002')
  expect(portapapeles).toContain('dogfood replay e2')
})

test('corridas → mosaico', async ({ page }) => {
  await page.goto('/proyectos/predicts/corridas')
  await expect(page.getByRole('heading', { name: 'Corridas', level: 1 })).toBeVisible()
  await foto(page, 'corridas')

  await page.getByRole('link', { name: /c1/ }).first().click()
  await expect(page).toHaveURL(/\/corridas\/c1/)
  await expect(page.getByRole('tab', { name: 'Acciones del agente' })).toBeVisible()
  await expect(page.getByTestId('tarjeta')).toHaveCount(3)
  await expect(page.locator('[data-grupo="exito"], [data-grupo]').first()).toBeVisible()
  await foto(page, 'corrida-mosaico')
})

test('insights', async ({ page }) => {
  await page.goto('/proyectos/predicts/insights')
  await expect(page.getByRole('heading', { name: 'Insights', level: 1 })).toBeVisible()
  await expect(page.getByText('Tasa de éxito').first()).toBeVisible()
  await expect(page.getByText('1 de 3 casos')).toBeVisible()
  await foto(page, 'insights')
})

test('suites y programaciones', async ({ page }) => {
  await page.goto('/suites')
  await expect(page.getByRole('heading', { name: 'Suites', level: 1 })).toBeVisible()
  await foto(page, 'suites')
  await page.goto('/programaciones')
  await expect(page.getByRole('heading', { name: 'Programaciones', level: 1 })).toBeVisible()
  await foto(page, 'programaciones')
})

test('ajustes → guardar', async ({ page }) => {
  await page.goto('/proyectos/predicts/ajustes/general')
  const guardar = page.getByRole('button', { name: 'Guardar cambios' })
  await expect(guardar).toBeDisabled()
  await page.getByRole('textbox', { name: /^Instrucciones/ }).fill('Enfócate en el login')
  await expect(guardar).toBeEnabled()
  await foto(page, 'ajustes')
  await guardar.click()
  await expect(page.getByRole('status')).toHaveText('Cambios guardados')
  await page.reload()
  await expect(page.getByRole('textbox', { name: /^Instrucciones/ })).toHaveValue('Enfócate en el login')
})
