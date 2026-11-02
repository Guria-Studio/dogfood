import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, createRouter, RouterProvider } from '@tanstack/react-router'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { routeTree } from '@/routeTree.gen'
import type { Insights } from './api'

const BASE: Insights = {
  corrida_id: 'c2', casos_fallaron: 2, prompt: 'Causas:\n1. Tabla vacía\n2. Sesión caduca',
  pasaron: 1, total: 3, abiertos: 2, arreglados: 1,
  regresiones: [{ tc: 'TC001', nombre: 'Caso a', ref: 'main@bbb2222' }],
  tendencia: [
    { corrida_id: 'c1', fecha: '2026-01-01', pasaron: 1, total: 3, tasa: 0.33, costo_usd: 1 },
    { corrida_id: 'c2', fecha: '2026-01-02', pasaron: 1, total: 3, tasa: 0.33, costo_usd: 2 },
  ],
  issues: [
    { huella: 'HB', titulo: 'Tabla vacía', ruta: '/b', gravedad: 'alta', casos: ['TC001', 'TC002'] },
    { huella: 'HA', titulo: 'Sesión caduca', ruta: '/a', gravedad: 'media', casos: ['TC003'] },
  ],
  friccion: [{ pantalla: '/b', n: 2, citas: ['No entiendo el botón'] }],
  oraculo: { correctas: 4, equivocadas: 1 },
  cobertura: [
    { caso_de_uso: 'subir', estado: 'brecha', ultimos: ['paso', 'fallo'], casos: 3, pasaron: 1, fallaron: 2, bloqueados: 0, porcentaje: 33, ultima: '2026-01-02T00:00:00' },
  ],
} // prettier-ignore

function montar(datos: Insights) {
  vi.stubGlobal('fetch', async (entrada: Request | string) => {
    const url = new URL(typeof entrada === 'string' ? entrada : entrada.url, 'http://x')
    if (url.pathname === '/api/proyectos/predicts/insights')
      return new Response(JSON.stringify(datos), { headers: { 'content-type': 'application/json' } })
    return new Response('{}', { status: 404, headers: { 'content-type': 'application/json' } })
  })
  const router = createRouter({ routeTree, history: createMemoryHistory({ initialEntries: ['/proyectos/predicts/insights'] }) })
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return router
}
afterEach(() => vi.unstubAllGlobals())

describe('insights', () => {
  it('cuenta la regresión con su ref y los arreglados', async () => {
    montar(BASE)
    const regresiones = await screen.findByRole('group', { name: 'Regresiones' })
    expect(regresiones).toHaveTextContent('1')
    expect(regresiones).toHaveTextContent('TC001 volvió en main@bbb2222')
    expect(screen.getByRole('group', { name: 'Arreglados' })).toHaveTextContent('1')
    expect(screen.getByRole('group', { name: 'Tasa de éxito' })).toHaveTextContent('1 de 3 casos')
  })

  it('agrupa los issues por huella con sus casos, el chip abre el sheet', async () => {
    const router = montar(BASE)
    await screen.findByText('2 casos')
    const grupo = document.querySelector('[data-huella="HB"]')!
    expect(grupo).toHaveTextContent('Tabla vacía')
    expect(grupo).toHaveTextContent('TC001')
    expect(grupo).toHaveTextContent('TC002')
    await userEvent.click(grupo.querySelector('button')!)
    expect(router.state.location.search).toMatchObject({ caso: 'TC001' })
  })

  it('copia el prompt de toda la corrida con todas las causas', async () => {
    const copiado = vi.fn().mockResolvedValue(undefined)
    const user = userEvent.setup()
    montar(BASE)
    await screen.findByText('2 casos fallaron en la última corrida')
    vi.spyOn(navigator.clipboard, 'writeText').mockImplementation(copiado)
    await user.click(screen.getByRole('button', { name: 'Copiar prompt de arreglo' }))
    expect(copiado).toHaveBeenCalledWith(expect.stringContaining('Tabla vacía'))
    expect(copiado).toHaveBeenCalledWith(expect.stringContaining('Sesión caduca'))
  })

  it('con una sola corrida avisa que la tendencia necesita una segunda', async () => {
    montar({ ...BASE, tendencia: BASE.tendencia.slice(0, 1) })
    expect(await screen.findByText('La tendencia necesita una segunda corrida')).toBeInTheDocument()
  })
})
