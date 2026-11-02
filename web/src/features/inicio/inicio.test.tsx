import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, createRootRoute, createRoute, createRouter, RouterProvider } from '@tanstack/react-router'
import { render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { Inicio } from './Inicio'

const proyecto = (extra = {}) => ({
  slug: 'predicts', nombre: 'predicts', tipo: 'web', creado: '2026-01-01T00:00:00Z',
  notificaciones: { slack: false, issues_github: true, repo: '' },
  ultimos: { corrida_id: null, pasaron: 0, fallaron: 0, ultima_actividad: null },
  ...extra,
})

function montar(lista: unknown[]) {
  vi.stubGlobal('fetch', async () => new Response(JSON.stringify(lista), { headers: { 'content-type': 'application/json' } }))
  const raiz = createRootRoute({
    component: () => (
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <Inicio />
      </QueryClientProvider>
    ),
  })
  const rutas = ['/', '/proyectos', '/proyectos/nuevo', '/ayuda'].map((path) => createRoute({ getParentRoute: () => raiz, path }))
  const router = createRouter({ routeTree: raiz.addChildren(rutas), history: createMemoryHistory({ initialEntries: ['/'] }) })
  render(<RouterProvider router={router} />)
}
afterEach(() => vi.unstubAllGlobals())

describe('inicio', () => {
  it('con proyecto y sin corridas son 1 de 4', async () => {
    montar([proyecto()])
    expect(await screen.findByText('1 de 4 hechas')).toBeInTheDocument()
    expect(document.querySelector('[data-paso="proyecto"]')).toHaveAttribute('data-hecho', 'true')
    expect(document.querySelector('[data-paso="corrida"]')).toHaveAttribute('data-hecho', 'false')
  })

  it('sin proyectos son 0 de 4 y con todo conectado 4 de 4', async () => {
    montar([])
    expect(await screen.findByText('0 de 4 hechas')).toBeInTheDocument()
  })

  it('con corrida, Slack y GitHub son 4 de 4', async () => {
    montar([
      proyecto({
        notificaciones: { slack: true, issues_github: true, repo: 'a/b' },
        ultimos: { corrida_id: 'c1', pasaron: 3, fallaron: 1, ultima_actividad: '2026-02-01T00:00:00Z' },
      }),
    ])
    expect(await screen.findByText('4 de 4 hechas')).toBeInTheDocument()
  })
})
