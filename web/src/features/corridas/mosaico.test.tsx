import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, createRouter, RouterProvider } from '@tanstack/react-router'
import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { routeTree } from '@/routeTree.gen'

class WsFalso {
  static todos: WsFalso[] = []
  onopen: (() => void) | null = null
  onmessage: ((m: { data: string }) => void) | null = null
  onclose: (() => void) | null = null
  constructor(public url: string) {
    WsFalso.todos.push(this)
  }
  close() {}
}

const caso = (n: number, estado: string, prioridad = 'alta') => ({
  id: `esc${n}:p${n}`, titulo: `Caso ${n}`, escenario_id: `esc${n}`, persona_id: `p${n}`,
  persona_nombre: `Persona ${n}`, objetivo: 'o', criterio_exito: 'c', prioridad, superficies: [],
  datos: null, ejecuciones: [`e${n}`], estado, ejecucion_id: `e${n}`, duracion_s: 5,
}) // prettier-ignore

const PLAN = [caso(1, 'en_curso'), caso(2, 'exito'), caso(3, 'fallo', 'media'), caso(4, 'no_concluyente')]

beforeEach(() => {
  WsFalso.todos = []
  vi.stubGlobal('WebSocket', WsFalso)
  vi.stubGlobal('fetch', async (entrada: Request | string) => {
    const url = new URL(typeof entrada === 'string' ? entrada : entrada.url, 'http://x')
    const json = (d: unknown) => new Response(JSON.stringify(d), { headers: { 'content-type': 'application/json' } })
    if (url.pathname === '/api/corridas/c1/plan') return json(PLAN)
    if (url.pathname === '/api/corridas/c1')
      return json({ resumen: { id: 'c1', objetivo: 'predicts', ref: 'main', version: 'v1', estado: 'en_curso', inicio: '2026-01-01T00:00:00', fin: null, n_personas: 4, ejecuciones: 4, por_resultado: {}, costo_usd: 0, costo_equivalente_usd: 0 }, comparacion: [] })
    if (url.pathname.startsWith('/api/ejecuciones/')) return new Response('no', { status: 404 })
    if (url.pathname === '/api/etiquetas') return json({})
    return new Response('no', { status: 404 })
  })
})
afterEach(() => vi.unstubAllGlobals())

async function montar(pestana: 'acciones' | 'lista' = 'acciones') {
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: [`/proyectos/predicts/corridas/c1?pestana=${pestana}`] }),
  })
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  await screen.findByText('Caso 1', {}, { timeout: 5000 })
}

const grupo = (clave: string) => document.querySelector(`[data-grupo="${clave}"]`) as HTMLElement
const conteo = (clave: string) => grupo(clave).querySelector('[data-conteo]')?.textContent
const casosEn = (clave: string) => [...grupo(clave).querySelectorAll('[data-caso]')].map((e) => e.textContent?.match(/Caso \d/)?.[0])

describe('mosaico de la corrida', () => {
  it('agrupa por estado con sus conteos y la tasa de éxito', async () => {
    await montar()
    expect(['corriendo', 'pasaron', 'fallaron', 'bloqueados'].map(conteo)).toEqual(['1', '1', '1', '1'])
    expect(casosEn('pasaron')).toEqual(['Caso 2'])
    expect(screen.getByText('25%')).toBeInTheDocument()
    expect(within(grupo('corriendo')).getByText('EN VIVO')).toBeInTheDocument()
  })

  it('un evento de websocket pasa una tarjeta de En vivo a Falló', async () => {
    await montar()
    expect(casosEn('corriendo')).toEqual(['Caso 1'])
    act(() =>
      WsFalso.todos[0].onmessage?.({
        data: JSON.stringify({ ejecucion_id: 'e1', tipo: 'fin', n_paso: 3, persona: 'Persona 1', escenario: 'esc1', paso_contrato: '', razonamiento: '', accion: '', resultado: 'fallo', ts: new Date().toISOString() }),
      }),
    )
    await waitFor(() => expect(casosEn('fallaron').sort()).toEqual(['Caso 1', 'Caso 3']))
    expect(conteo('corriendo')).toBe('0')
    expect(screen.queryByText('EN VIVO')).not.toBeInTheDocument()
  })

  it('el filtro por estado funciona', async () => {
    await montar()
    await userEvent.selectOptions(screen.getByLabelText('Estado'), 'fallo')
    expect(casosEn('fallaron')).toEqual(['Caso 3'])
    expect(conteo('pasaron')).toBe('0')
  })

  it('la lista y el mosaico muestran los mismos casos', async () => {
    await montar()
    const mosaico = [...document.querySelectorAll('[data-testid="tarjeta"]')].map((e) => e.getAttribute('data-caso')).sort()
    expect(mosaico).toHaveLength(4)
    await userEvent.click(screen.getByRole('tab', { name: 'Lista' }))
    await waitFor(() => expect(document.querySelectorAll('tr[data-caso]')).toHaveLength(4))
    const lista = [...document.querySelectorAll('tr[data-caso]')].map((e) => e.getAttribute('data-caso')).sort()
    expect(lista).toEqual(mosaico)
  })
})
