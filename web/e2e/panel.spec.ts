import { expect, test } from '@playwright/test'

test('corridas: filtrar y abrir una ejecución, pasos con teclado, diálogo de issue', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'Corridas', level: 1 })).toBeVisible()
  await expect(page.getByRole('row', { name: /Bob/ })).toBeVisible()

  await page.getByLabel('resultado', { exact: true }).selectOption('aprobado')
  await expect(page).toHaveURL(/resultado=aprobado/)
  await expect(page.getByRole('row', { name: /Ana/ })).toBeVisible()
  await expect(page.getByRole('row', { name: /Bob/ })).toHaveCount(0)

  await page.goto('/')
  await page.getByRole('row', { name: /Bob/ }).click()
  await expect(page).toHaveURL(/\/ejecuciones\/e2$/)
  await expect(page.getByRole('heading', { name: 'Ejecución e2' })).toBeVisible()

  const timeline = page.getByRole('navigation', { name: 'Línea de tiempo' })
  await expect(timeline.getByRole('button', { name: 'Paso 1' })).toHaveAttribute('aria-current', 'step')
  await page.keyboard.press('ArrowRight')
  await expect(timeline.getByRole('button', { name: 'Paso 2' })).toHaveAttribute('aria-current', 'step')
  await expect(page.getByText('porque 2')).toBeVisible()
  await page.keyboard.press('ArrowLeft')
  await expect(timeline.getByRole('button', { name: 'Paso 1' })).toHaveAttribute('aria-current', 'step')

  await page.getByRole('button', { name: 'Crear issue' }).click()
  await expect(page.getByRole('heading', { name: '¿Crear el issue?' })).toBeVisible()
  await page.getByRole('button', { name: 'Cancelar' }).click()
  await expect(page.getByRole('heading', { name: '¿Crear el issue?' })).toHaveCount(0)
})

test('recorridos', async ({ page }) => {
  await page.goto('/recorridos')
  await expect(page.getByRole('heading', { level: 1, name: /Recorridos/ })).toBeVisible()
  await expect(page.getByText('login-fallido').first()).toBeVisible()
})

test('dispositivos vacío', async ({ page }) => {
  await page.goto('/dispositivos')
  await expect(page.getByText('No hay dispositivos')).toBeVisible()
})

test('ayuda: buscar «glosario» y abrir el documento', async ({ page }) => {
  await page.goto('/ayuda')
  await page.getByLabel('Buscar en la ayuda').fill('glosario')
  await page.getByRole('link', { name: 'Glosario' }).first().click()
  await expect(page).toHaveURL(/\/ayuda\/glosario$/)
  await expect(page.getByRole('heading', { name: 'Glosario', level: 1 })).toBeVisible()
})

test('el ⓘ de la ejecución lleva a su ayuda', async ({ page }) => {
  await page.goto('/ejecuciones/e1')
  await page.getByRole('link', { name: 'Ayuda de esta pantalla' }).click()
  await expect(page).toHaveURL(/\/ayuda\?pantalla=ejecucion/)
  await expect(page.getByLabel('Ayuda para esta pantalla')).toBeVisible()
})

test('tema oscuro', async ({ page }) => {
  await page.goto('/')
  const html = page.locator('html')
  await expect(html).not.toHaveClass(/dark/)
  await page.getByRole('button', { name: 'Cambiar a tema oscuro' }).click()
  await expect(html).toHaveClass(/dark/)
  await page.reload()
  await expect(html).toHaveClass(/dark/)
})
