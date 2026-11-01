import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { TarjetaSugerencia } from './TarjetaSugerencia'

beforeEach(() => {
  vi.stubGlobal('fetch', async (entrada: Request | string) => {
    const url = new URL(typeof entrada === 'string' ? entrada : entrada.url, 'http://x')
    if (url.pathname === '/api/ejecuciones/c1-E1/hallazgos')
      return new Response(
        JSON.stringify([
          {
            id: 'c1-H1', titulo: '404 en /calidad', pantalla: '/calidad', gravedad: 'alta',
            ejecucion_id: 'c1-E1', commit: 'abc1234', repo: 'yo/predicts',
            sugerencia: {
              causa: 'falta registrar la ruta', cambio: 'agregar @get("/calidad")', confianza: 'media',
              archivos: [{ ruta: 'src/rutas.py', linea: 3 }],
            },
          },
        ]),
        { headers: { 'content-type': 'application/json' } },
      )
    return new Response('no', { status: 404 })
  })
})
afterEach(() => vi.unstubAllGlobals())

describe('tarjeta de sugerencia', () => {
  it('muestra causa, archivos y confianza', async () => {
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <TarjetaSugerencia ejecucionId="c1-E1" />
      </QueryClientProvider>,
    )
    await screen.findByText(/Posible causa y arreglo/)
    expect(screen.getByText(/falta registrar la ruta/)).toBeInTheDocument()
    expect(screen.getByText(/confianza media/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'src/rutas.py:3' })).toHaveAttribute(
      'href',
      'https://github.com/yo/predicts/blob/abc1234/src/rutas.py#L3',
    )
  })
})
