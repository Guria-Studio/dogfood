import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, createRootRoute, createRoute, createRouter, RouterProvider } from '@tanstack/react-router'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { PantallaReporte } from './PantallaReporte'

const json = (d: unknown) => new Response(JSON.stringify(d), { headers: { 'content-type': 'application/json' } })
const hallazgo = (n: number, gravedad: string) => ({
  id: `c1-H${n}`, titulo: `Hallazgo ${n}`, pantalla: '/panel', gravedad, ejecucion_id: `c1-E${n}`,
  commit: '', repo: '', sugerencia: null,
})

beforeEach(() => {
  vi.stubGlobal('fetch', async (entrada: Request | string) => {
    const url = new URL(typeof entrada === 'string' ? entrada : entrada.url, 'http://localhost')
    if (url.pathname === '/api/corridas/c1')
      return json({
        resumen: {
          id: 'c1', objetivo: 'predicts', ref: 'main', version: 'abc', estado: 'completa',
          inicio: '2026-01-01T10:00:00', fin: '2026-01-01T10:10:00', n_personas: 4, ejecuciones: 4,
          por_resultado: { aprobado: 3, fallo: 1, no_concluyente: 0 }, costo_usd: 1.5, costo_equivalente_usd: 2,
        },
        comparacion: [],
      })
    if (url.pathname === '/api/corridas/c1/reporte')
      return json({
        hallazgos: [hallazgo(1, 'alta'), hallazgo(2, 'media')],
        fallidos: [{ ejecucion_id: 'c1-E1', titulo: 'demo', persona: 'Ana', resultado: 'fallo', miniatura: null }],
        opiniones: [{ pantalla: '/panel', total: 1, citas: [{ texto: 't', cita: 'no veo nada', severidad: 'alta' }] }],
      })
    return new Response('no', { status: 404 })
  })
})
afterEach(() => vi.unstubAllGlobals())

function montar() {
  const raiz = createRootRoute({
    component: () => (
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <PantallaReporte id="c1" />
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
}

describe('reporte', () => {
  it('muestra tasa de éxito, conteos por estado y gravedad y las citas', async () => {
    montar()
    expect(await screen.findByRole('img', { name: 'Tasa de éxito 75%' })).toBeInTheDocument()
    expect(document.querySelector('[data-estado="aprobado"]')).toHaveTextContent('3')
    expect(document.querySelector('[data-estado="fallo"]')).toHaveTextContent('1')
    expect(document.querySelector('[data-gravedad="alta"]')).toHaveTextContent('alta: 1')
    expect(document.querySelector('[data-gravedad="media"]')).toHaveTextContent('media: 1')
    expect(screen.getByText(/no veo nada/)).toBeInTheDocument()
  })

  it('«Copiar resumen» deja el texto con los conteos en el portapapeles', async () => {
    const user = userEvent.setup()
    montar()
    await user.click(await screen.findByRole('button', { name: /Copiar resumen/ }))
    const texto = await navigator.clipboard.readText()
    expect(texto).toContain('éxito 75% (3 aprobados, 1 fallidos, 0 no concluyentes)')
    expect(texto).toContain('[alta] Hallazgo 1')
    expect(texto).not.toContain('Hallazgo 2')
    expect(texto).toContain('/corridas/c1/reporte')
  })
})
