import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
} from '@tanstack/react-router'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { NuevaCorrida } from './NuevaCorrida'
import { Progreso } from './Progreso'

const pedidos: { metodo: string; ruta: string; header: string | null; cuerpo: string }[] = []
let terminados = 1

beforeEach(() => {
  pedidos.length = 0
  terminados = 1
  vi.stubGlobal('fetch', async (entrada: Request | URL | string, init?: RequestInit) => {
    const req = entrada instanceof Request ? entrada : new Request(entrada, init)
    const url = new URL(req.url)
    pedidos.push({
      metodo: req.method,
      ruta: url.pathname,
      header: req.headers.get('X-Dogfood'),
      cuerpo: req.method === 'POST' ? await req.text() : '',
    })
    const json = (d: unknown) => Response.json(d)
    if (url.pathname === '/api/recorridos')
      return json([
        { id: 'login', titulo: 'Login', driver: 'web', contrato: '', por_resultado: {} },
        { id: 'subir', titulo: 'Subir archivo', driver: 'web', contrato: '', por_resultado: {} },
      ])
    if (url.pathname === '/api/corridas' && req.method === 'POST') return json({ id: 'L-1' })
    if (url.pathname === '/api/corridas/L-1/estado')
      return json({
        id: 'L-1', estado: 'activa', corrida_id: 'c1', terminados, total: 4,
        en_curso: ['Caso de login'], log: ['línea 1'],
      })
    if (url.pathname === '/api/corridas/L-1/cancelar') return json({ id: 'L-1', estado: 'cancelada' })
    return new Response('no', { status: 404 })
  })
})
afterEach(() => vi.unstubAllGlobals())

function montar(componente: () => React.JSX.Element) {
  const raiz = createRootRoute({
    component: () => (
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        {componente()}
      </QueryClientProvider>
    ),
  })
  const router = createRouter({
    routeTree: raiz.addChildren([
      createRoute({ getParentRoute: () => raiz, path: '/' }),
      createRoute({ getParentRoute: () => raiz, path: '/vista' }),
      createRoute({ getParentRoute: () => raiz, path: '/corridas/$id' }),
      createRoute({ getParentRoute: () => raiz, path: '/lanzamientos/$id' }),
    ]),
    history: createMemoryHistory({ initialEntries: ['/'] }),
  })
  render(<RouterProvider router={router} />)
  return router
}

describe('acciones', () => {
  it('el formulario manda lo elegido y abre el progreso', async () => {
    const router = montar(() => <NuevaCorrida />)
    const u = userEvent.setup()
    await u.click(await screen.findByRole('button', { name: /nueva corrida/i }))
    await u.selectOptions(await screen.findByLabelText('Escenarios'), ['subir'])
    await u.clear(screen.getByLabelText('Personas'))
    await u.type(screen.getByLabelText('Personas'), '5')
    await u.clear(screen.getByLabelText('Ref'))
    await u.type(screen.getByLabelText('Ref'), 'master')
    expect(screen.queryByRole('alert')).toBeNull()
    await u.click(screen.getByLabelText(/publicar los hallazgos/i))
    expect(screen.getByRole('alert')).toHaveTextContent(/publica en GitHub/)
    await u.click(screen.getByLabelText(/publicar los hallazgos/i))
    await u.click(screen.getByRole('button', { name: 'Lanzar' }))
    await waitFor(() => expect(pedidos.some((p) => p.metodo === 'POST')).toBe(true))
    const p = pedidos.find((x) => x.metodo === 'POST')!
    expect(p.header).toBe('1')
    expect(JSON.parse(p.cuerpo)).toMatchObject({
      objetivo: 'predicts', ref: 'master', personas: 5, escenarios: ['subir'], sin_publicar: true,
    })
    await waitFor(() => expect(router.state.location.pathname).toBe('/lanzamientos/L-1'))
  })

  it('el progreso se actualiza y permite cancelar', async () => {
    montar(() => <Progreso id="L-1" />)
    expect(await screen.findByText('1 de 4 casos terminados')).toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '25')
    expect(screen.getByText('En curso: Caso de login')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Vista en vivo' })).toBeInTheDocument()
    terminados = 3
    expect(await screen.findByText('3 de 4 casos terminados', {}, { timeout: 4000 })).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Cancelar' }))
    await waitFor(() => expect(pedidos.some((p) => p.ruta.endsWith('/cancelar') && p.header === '1')).toBe(true))
  })
})
