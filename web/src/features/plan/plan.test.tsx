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

import { TablaCasos } from './TablaCasos'

const caso = (id: string, estado: string, prioridad: string, ejecucion_id: string | null) => ({
  id, titulo: `Caso ${id}`, escenario_id: id, persona_id: 'P001', persona_nombre: 'Ana',
  objetivo: 'o', criterio_exito: 'c', prioridad, superficies: [], datos: null,
  ejecuciones: ejecucion_id ? [ejecucion_id] : ['x'], estado, ejecucion_id,
  duracion_s: ejecucion_id ? 65 : null,
})

beforeEach(() => {
  vi.stubGlobal('fetch', async (entrada: Request | string) => {
    const url = new URL(typeof entrada === 'string' ? entrada : entrada.url, 'http://x')
    if (url.pathname === '/api/corridas/c1/plan')
      return new Response(
        JSON.stringify([
          caso('subir', 'exito', 'alta', 'c1-E1'),
          caso('demo', 'fallo', 'alta', 'c1-E2'),
          caso('login', 'pendiente', 'media', null),
        ]),
        { headers: { 'content-type': 'application/json' } },
      )
    return new Response('no', { status: 404 })
  })
})
afterEach(() => vi.unstubAllGlobals())

function montar() {
  const raiz = createRootRoute({
    component: () => (
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <TablaCasos corridaId="c1" />
      </QueryClientProvider>
    ),
  })
  const router = createRouter({
    routeTree: raiz.addChildren([
      createRoute({ getParentRoute: () => raiz, path: '/' }),
      createRoute({ getParentRoute: () => raiz, path: '/ejecuciones/$id' }),
    ]),
    history: createMemoryHistory({ initialEntries: ['/'] }),
  })
  render(<RouterProvider router={router} />)
  return router
}

describe('casos de prueba', () => {
  it('muestra los casos con su badge y filtra por estado', async () => {
    montar()
    await screen.findByText('Caso subir')
    expect(document.querySelectorAll('[data-caso]')).toHaveLength(3)
    expect(document.querySelector('[data-caso="subir"] [data-estado="exito"]')).toHaveTextContent('Éxito')
    expect(document.querySelector('[data-caso="demo"] [data-estado="fallo"]')).toHaveTextContent('Fallo')
    expect(document.querySelector('[data-caso="login"] [data-estado="pendiente"]')).toHaveTextContent('Pendiente')
    expect(screen.getAllByText('1 min 5 s')).toHaveLength(2)

    await userEvent.selectOptions(screen.getByLabelText('Estado'), 'fallo')
    expect(document.querySelectorAll('[data-caso]')).toHaveLength(1)
    expect(screen.getByText('Caso demo')).toBeInTheDocument()

    await userEvent.selectOptions(screen.getByLabelText('Estado'), '')
    await userEvent.selectOptions(screen.getByLabelText('Prioridad'), 'media')
    expect(document.querySelectorAll('[data-caso]')).toHaveLength(1)
    expect(screen.getByText('Caso login')).toBeInTheDocument()
  })

  it('el clic en un caso abre su ejecución', async () => {
    const router = montar()
    await userEvent.click(await screen.findByText('Caso demo'))
    await waitFor(() => expect(router.state.location.pathname).toBe('/ejecuciones/c1-E2'))
  })
})
