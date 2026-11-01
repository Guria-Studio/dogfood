import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
} from '@tanstack/react-router'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { TooltipProvider } from '@/components/ui/tooltip'
import { PantallaCorrida } from './PantallaCorrida'
import { PantallaCorridas } from './PantallaCorridas'
import { validarFiltros } from './TablaEjecuciones'

const fila = (id: string, resultado: string) => ({
  id, corrida_id: 'c1', fecha: '2026-11-01T10:00:00', version: 'v1', persona_id: 'p1',
  persona_nombre: 'Ana', persona_idioma: 'es', escenario_id: 'login', driver: 'web',
  motor: 'api', backend: 'anthropic', modelo: 'sonnet', resultado, duracion_s: 12,
  pasos: 5, tokens: 100, capturas: 3, costo_usd: 0.5, costo_equivalente_usd: 0.5,
})

const etiquetas = { aprobado: 'Éxito', rendido: 'Rendido', fallo: 'Fallo', no_concluyente: 'No concluyente' }
let ejecuciones: unknown[] = []
const pedidos: string[] = []

beforeEach(() => {
  pedidos.length = 0
  vi.stubGlobal('fetch', async (entrada: Request | string) => {
    const url = new URL(typeof entrada === 'string' ? entrada : entrada.url, 'http://x')
    pedidos.push(url.pathname + url.search)
    const json = (d: unknown) => new Response(JSON.stringify(d), { headers: { 'content-type': 'application/json' } })
    if (url.pathname === '/api/ejecuciones') return json(ejecuciones)
    if (url.pathname === '/api/etiquetas') return json(etiquetas)
    if (url.pathname === '/api/filtros')
      return json({ resultado: [{ valor: 'fallo', etiqueta: 'Fallo' }] })
    if (url.pathname === '/api/corridas/c1')
      return json({
        resumen: {
          id: 'c1', objetivo: 'predicts', ref: 'main', version: 'v1', estado: 'terminada',
          inicio: '2026-11-01T10:00:00', fin: '2026-11-01T10:02:00', n_personas: 3,
          ejecuciones: 4, por_resultado: { aprobado: 3, fallo: 1 }, costo_usd: 1.5,
          costo_equivalente_usd: 2,
        },
        comparacion: [{
          motor: 'claude_code', backend: 'cli', modelo: 'opus', ejecuciones: 4, aprobadas: 3,
          fallidas: 1, no_concluyentes: 0, tasa_aprobacion: 0.75, tokens: 10, costo_usd: 0.4,
          costo_equivalente_usd: 0.5,
        }],
      })
    return new Response('no', { status: 404 })
  })
})
afterEach(() => vi.unstubAllGlobals())

async function montar(componente: () => React.ReactElement, inicial = '/') {
  const raiz = createRootRoute({
    component: () => (
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <TooltipProvider>{componente()}</TooltipProvider>
      </QueryClientProvider>
    ),
  })
  const rutas = [
    createRoute({ getParentRoute: () => raiz, path: '/', validateSearch: validarFiltros }),
    ...['/corridas/$id', '/ejecuciones/$id', '/ayuda/$slug', '/ayuda'].map((path) =>
      createRoute({ getParentRoute: () => raiz, path }),
    ),
  ]
  const router = createRouter({
    routeTree: raiz.addChildren(rutas),
    history: createMemoryHistory({ initialEntries: [inicial] }),
  })
  render(<RouterProvider router={router} />)
  return router
}

describe('corridas', () => {
  it('la tabla muestra las filas y el badge correcto por resultado', async () => {
    ejecuciones = ['aprobado', 'rendido', 'fallo', 'no_concluyente'].map((r, i) => fila(`e${i}`, r))
    await montar(() => <PantallaCorridas />)
    const filas = await screen.findAllByRole('row')
    expect(filas).toHaveLength(5)
    for (const [i, r] of ['aprobado', 'rendido', 'fallo', 'no_concluyente'].entries()) {
      const badge = within(filas[i + 1]).getByText(etiquetas[r as keyof typeof etiquetas], {
        selector: '[data-resultado]',
      })
      expect(badge).toHaveAttribute('data-resultado', r)
    }
  })

  it('cambiar un filtro actualiza la URL y vuelve a pedir con ese parámetro', async () => {
    ejecuciones = [fila('e0', 'fallo')]
    const router = await montar(() => <PantallaCorridas />)
    await screen.findAllByRole('row')
    await screen.findByRole('option', { name: 'Fallo' })
    await userEvent.selectOptions(screen.getByLabelText('resultado'), 'fallo')
    await waitFor(() => expect(router.state.location.search).toEqual({ resultado: 'fallo' }))
    await waitFor(() => expect(pedidos).toContain('/api/ejecuciones?resultado=fallo'))
  })

  it('sin filas muestra el estado vacío con el link a la ayuda', async () => {
    ejecuciones = []
    await montar(() => <PantallaCorridas />)
    const link = await screen.findByRole('link', { name: 'Cómo correr dogfood' })
    expect(link).toHaveAttribute('href', '/ayuda/primera-corrida')
  })

  it('la corrida muestra el costo con dos decimales y la tabla de motores', async () => {
    await montar(() => <PantallaCorrida id="c1" />)
    expect(await screen.findByText('$1.50')).toBeInTheDocument()
    expect(screen.getByText('Comparación de motores')).toBeInTheDocument()
    expect(screen.getByText('claude_code')).toBeInTheDocument()
    expect(screen.getAllByText('75%')).toHaveLength(2)
  })
})
