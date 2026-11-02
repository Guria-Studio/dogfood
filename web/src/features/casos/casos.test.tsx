import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, createRouter, RouterProvider } from '@tanstack/react-router'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { routeTree } from '@/routeTree.gen'
import type { CasoFila, DetalleCaso } from './api'

const fila = (tc: string, estado: CasoFila['estado'], uso: string, falla = ''): CasoFila => ({
  tc, id: `${uso}:p1`, nombre: `Caso ${tc}`, caso_de_uso: uso, prioridad: 'alta', estado,
  fecha: '2026-01-01T00:00:00', falla, ejecucion_id: `c1-${tc}`,
  persona: { id: 'p1', nombre: 'Ana Pérez', idioma: 'es', destreza: 2, iniciales: 'AP' },
}) // prettier-ignore

const CASOS = [
  fila('TC001', 'paso', 'subir'),
  fila('TC002', 'fallo', 'subir', 'No apareció la tabla.'),
  fila('TC003', 'paso', 'exportar'),
]

const PROMPT = 'Un test de usuario de dogfood falló.\n## Evidencia (redactada)\n- key=«redactado»\ndogfood replay c1-TC002'

const DETALLE: DetalleCaso = {
  ...CASOS[1],
  objetivo: 'Subir el CSV', criterio_exito: 've la tabla', video: null,
  pasos: [
    { n: 1, url: '/', pantalla: '/', accion: 'abrir', captura: null, razonamiento: '', paso_contrato: '', esperado: '', observado: '', consola: [], red: [] },
    { n: 2, url: '/subir', pantalla: '/subir', accion: 'subir csv', captura: null, razonamiento: '', paso_contrato: '', esperado: '', observado: 'error 500', consola: [], red: [] },
  ],
  ajustes: { Viewport: 'escritorio' },
  historial: [{ ejecucion_id: 'c1-TC002', corrida_id: 'c1', estado: 'fallo', error: 'No apareció la tabla.', fecha: '2026-01-01' }],
  opinion: [], verificaciones: [], codigo: null, lenguaje_codigo: null,
  falla_detalle: {
    error: 'No apareció la tabla.', hallazgo_id: 'c1-H1', prompt: PROMPT,
    sugerencia: { causa: 'El parser no acepta comas', cambio: 'Normalizar el separador', confianza: 'media', archivos: [{ ruta: 'api/subir.py', linea: 42 }] },
  },
} // prettier-ignore

beforeEach(() => {
  vi.stubGlobal('fetch', async (entrada: Request | string) => {
    const url = new URL(typeof entrada === 'string' ? entrada : entrada.url, 'http://x')
    const json = (d: unknown) => new Response(JSON.stringify(d), { headers: { 'content-type': 'application/json' } })
    if (url.pathname === '/api/proyectos/predicts/casos') {
      const estado = url.searchParams.get('estado')
      const casos = CASOS.filter((c) => !estado || c.estado === estado)
      const grupos = [...new Set(casos.map((c) => c.caso_de_uso))].map((u) => ({
        caso_de_uso: u,
        casos: casos.filter((c) => c.caso_de_uso === u),
      }))
      return json({ conteos: { paso: 2, fallo: 1 }, total: 3, grupos })
    }
    if (url.pathname === '/api/proyectos/predicts/casos/TC002') return json(DETALLE)
    if (url.pathname === '/api/ejecuciones') return json([])
    if (url.pathname === '/api/etiquetas' || url.pathname === '/api/filtros') return json({})
    return new Response('no', { status: 404 })
  })
})
afterEach(() => vi.unstubAllGlobals())

function montar(inicial = '/proyectos/predicts/casos') {
  const router = createRouter({ routeTree, history: createMemoryHistory({ initialEntries: [inicial] }) })
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return router
}

const filas = () => [...document.querySelectorAll('[data-caso]')].map((e) => e.getAttribute('data-caso'))

describe('casos de prueba', () => {
  it('las pestañas muestran los conteos y ?estado=fallo deja solo los fallidos', async () => {
    const user = userEvent.setup()
    const router = montar()
    await screen.findByText('Caso TC001')
    expect(filas()).toEqual(['TC001', 'TC002', 'TC003'])
    const fallaron = screen.getByRole('tab', { name: /Fallaron/ })
    expect(fallaron).toHaveTextContent('1')
    expect(screen.getByRole('tab', { name: /Todos/ })).toHaveTextContent('3')
    expect(screen.getByText('No apareció la tabla.')).toHaveClass('text-danger')

    await user.click(fallaron)
    await waitFor(() => expect(router.state.location.search).toMatchObject({ estado: 'fallo' }))
    await waitFor(() => expect(filas()).toEqual(['TC002']))
  })

  it('un grupo se colapsa', async () => {
    const user = userEvent.setup()
    montar()
    await screen.findByText('Caso TC001')
    const grupo = document.querySelector('[data-grupo="subir"]') as HTMLElement
    const cabecera = within(grupo).getByRole('button', { name: /subir/ })
    expect(cabecera).toHaveAttribute('aria-expanded', 'true')
    await user.click(cabecera)
    expect(cabecera).toHaveAttribute('aria-expanded', 'false')
    expect(filas()).toEqual(['TC003'])
  })

  it('el clic en una fila abre el sheet con ?caso= y Escape lo cierra', async () => {
    const user = userEvent.setup()
    const router = montar()
    await user.click(await screen.findByText('Caso TC002'))
    await waitFor(() => expect(router.state.location.search).toMatchObject({ caso: 'TC002' }))
    const sheet = await screen.findByRole('dialog')
    expect(await within(sheet).findByRole('heading', { name: 'Caso TC002' })).toBeInTheDocument()
    expect(within(sheet).getByRole('link', { name: /Expandir/ })).toHaveAttribute('href', '/proyectos/predicts/casos/TC002')

    await user.keyboard('{Escape}')
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(router.state.location.search).not.toHaveProperty('caso')
  })

  it('el caso fallido muestra Error, Causa y Arreglo y copia el prompt con dogfood replay', async () => {
    const user = userEvent.setup()
    montar('/proyectos/predicts/casos?caso=TC002')
    const sheet = await screen.findByRole('dialog')
    await within(sheet).findByRole('tab', { name: 'Error' })
    expect(within(sheet).getByRole('tabpanel', { name: 'Error' })).toHaveTextContent('No apareció la tabla.')
    expect(sheet.querySelector('[data-paso-fallido]')).toHaveTextContent('subir csv')

    await user.click(within(sheet).getByRole('tab', { name: 'Causa' }))
    expect(within(sheet).getByText('El parser no acepta comas')).toBeInTheDocument()
    await user.click(within(sheet).getByRole('tab', { name: 'Arreglo' }))
    expect(within(sheet).getByText(/sugerido por IA/)).toBeInTheDocument()
    expect(within(sheet).getByText('Normalizar el separador')).toBeInTheDocument()

    await user.click(within(sheet).getByRole('button', { name: /Copiar prompt de arreglo/ }))
    const copiado = await navigator.clipboard.readText()
    expect(copiado).toContain('dogfood replay c1-TC002')
    expect(copiado).not.toContain('sk-')

    await user.click(within(sheet).getByRole('tab', { name: 'Código' }))
    expect(within(sheet).getByText('Todavía no se exportó')).toBeInTheDocument()
    await user.click(within(sheet).getByRole('tab', { name: 'Historial' }))
    expect(within(sheet).getByRole('link', { name: 'Ver ejecución' })).toHaveAttribute(
      'href',
      '/proyectos/predicts/ejecuciones/c1-TC002',
    )
  })

  it('expandir abre el caso a pantalla completa', async () => {
    montar('/proyectos/predicts/casos/TC002')
    expect(await screen.findByRole('heading', { name: 'Caso TC002' })).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).toBeNull()
  })
})
