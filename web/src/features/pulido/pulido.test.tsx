import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, createRouter, RouterProvider } from '@tanstack/react-router'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { routeTree } from '@/routeTree.gen'

const fila = (n: number, corrida: string, resultado: string, costo: number) => ({
  id: `e${n}`, corrida_id: corrida, fecha: `2026-10-${String(n % 28 + 1).padStart(2, '0')}T10:00:00`,
  version: 'v1', persona_id: `p${n}`, persona_nombre: `Persona ${String(n).padStart(2, '0')}`,
  persona_idioma: 'es', escenario_id: 'login', driver: 'web', motor: 'api', backend: 'anthropic',
  modelo: 'sonnet', resultado, duracion_s: 10, pasos: n, tokens: 100, capturas: 1, costo_usd: costo,
  costo_equivalente_usd: costo,
})

let ejecuciones: unknown[] = []

beforeEach(() => {
  localStorage.clear()
  vi.stubGlobal('fetch', async (entrada: Request | string) => {
    const url = new URL(typeof entrada === 'string' ? entrada : entrada.url, 'http://x')
    const json = (d: unknown) => new Response(JSON.stringify(d), { headers: { 'content-type': 'application/json' } })
    if (url.pathname === '/api/ejecuciones') return json(ejecuciones)
    if (url.pathname === '/api/etiquetas') return json({})
    if (url.pathname === '/api/filtros') return json({})
    if (url.pathname.startsWith('/api/ayuda')) return json([])
    if (url.pathname === '/api/corridas/c2')
      return json({
        resumen: {
          id: 'c2', objetivo: 'predicts', ref: 'main', version: 'v1', estado: 'terminada',
          inicio: '2026-10-02T10:00:00', fin: null, n_personas: 2, ejecuciones: 2,
          por_resultado: {}, costo_usd: 1.25, costo_equivalente_usd: 1.25,
        },
        comparacion: [],
      })
    return new Response('no', { status: 404 })
  })
})
afterEach(() => vi.unstubAllGlobals())

function montar(inicial = '/') {
  const router = createRouter({ routeTree, history: createMemoryHistory({ initialEntries: [inicial] }) })
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return router
}

describe('pulido', () => {
  it('⌘K abre la paleta; «ayuda» + Enter navega a /ayuda', async () => {
    ejecuciones = []
    const router = montar()
    await screen.findByRole('heading', { name: 'Corridas' })
    const user = userEvent.setup()
    await user.keyboard('{Meta>}k{/Meta}')
    const entrada = await screen.findByPlaceholderText(/Ir a una pantalla/)
    await user.type(entrada, 'ayuda')
    await user.keyboard('{Enter}')
    await waitFor(() => expect(router.state.location.pathname).toBe('/ayuda'))
  })

  it('la tabla ordena por columna al hacer clic en el encabezado y pagina de a 20', async () => {
    ejecuciones = Array.from({ length: 25 }, (_, i) => fila(i + 1, 'c1', 'aprobado', 0.1))
    montar()
    const user = userEvent.setup()
    const tabla = await screen.findByRole('table')
    const cuerpo = () => within(tabla).getAllByRole('row').slice(1)
    expect(cuerpo()).toHaveLength(20)
    expect(screen.getByText(/página 1 de 2/)).toBeInTheDocument()

    await user.click(within(tabla).getByRole('button', { name: /Persona/ }))
    expect(within(tabla).getByRole('columnheader', { name: /Persona/ })).toHaveAttribute('aria-sort', 'ascending')
    expect(cuerpo()[0]).toHaveTextContent('Persona 01')
    await user.click(within(tabla).getByRole('button', { name: /Persona/ }))
    expect(cuerpo()[0]).toHaveTextContent('Persona 25')

    await user.click(screen.getByRole('button', { name: 'Siguiente' }))
    expect(cuerpo()).toHaveLength(5)
    expect(screen.getByText(/página 2 de 2/)).toBeInTheDocument()
  })

  it('la portada muestra las 4 tarjetas de KPI con los valores calculados', async () => {
    ejecuciones = [
      fila(1, 'c1', 'aprobado', 0.5),
      fila(2, 'c1', 'fallo', 0.5),
      fila(3, 'c2', 'aprobado', 0.75),
      fila(4, 'c2', 'rendido', 0.5),
    ]
    montar()
    const kpi = async (nombre: string) => (await screen.findByRole('group', { name: nombre })).querySelector('[data-kpi-valor]')
    expect(await kpi('Tasa de éxito')).toHaveTextContent('50%')
    expect(await kpi('Hallazgos')).toHaveTextContent('2')
    await waitFor(async () => expect(await kpi('Costo de la última corrida')).toHaveTextContent('$1.25'))
    expect(await kpi('Ejecuciones totales')).toHaveTextContent('4')
  })

  it('una ruta inexistente muestra la página 404', async () => {
    montar('/no-existe')
    expect(await screen.findByText('Página no encontrada')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ir a corridas' })).toHaveAttribute('href', '/')
  })
})
