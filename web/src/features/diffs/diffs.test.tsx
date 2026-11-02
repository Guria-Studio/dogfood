import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, createRouter, RouterProvider } from '@tanstack/react-router'
import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { routeTree } from '@/routeTree.gen'
import type { Diff, ResumenDiff } from './api'

const RESUMEN: ResumenDiff = {
  id: 'diff-1',
  proyecto: 'predicts',
  base: 'master',
  nueva: 'pr-7',
  creado: '2026-01-01T00:00:00+00:00',
  total: 2,
  con_cambios: 1,
}
const DIFF: Diff = {
  id: 'diff-1', proyecto: 'predicts', base: 'master', nueva: 'pr-7', creado: RESUMEN.creado,
  casos: [
    { tc: 'TC002', caso_id: 'b', titulo: 'Sin nada', resultado: 'sin_cambios', pasos: [] },
    { tc: 'TC001', caso_id: 'a', titulo: 'Alta', resultado: 'cambios', pasos: [{
      step_id: 's1', accion: 'click', capturas: { antes: 'capturas/TC001/s1-antes.png', despues: 'capturas/TC001/s1-despues.png' },
      cambios: [
        { tipo: 'red', subtipo: 'estado', gravedad: 'alta', metodo: 'GET', ruta: '/api/x', antes: 200, despues: 500 },
        { tipo: 'texto', gravedad: 'media', antes: 'Hola', despues: 'Adiós' },
        { tipo: 'consola', gravedad: 'media', texto: 'TypeError' },
        { tipo: 'visual', gravedad: 'baja', detalle: 'la captura difiere' },
      ],
    }] },
  ],
} // prettier-ignore

function montar(ruta: string) {
  vi.stubGlobal('fetch', async (entrada: Request | string) => {
    const url = new URL(entrada instanceof Request ? entrada.url : String(entrada), 'http://x')
    const json = (d: unknown) =>
      new Response(JSON.stringify(d), {
        headers: { 'content-type': 'application/json' },
      })
    if (url.pathname === '/api/proyectos/predicts/diffs') return json([RESUMEN])
    if (url.pathname === '/api/diffs/diff-1') return json(DIFF)
    return new Response('{}', {
      status: 404,
      headers: { 'content-type': 'application/json' },
    })
  })
  const router = createRouter({
    routeTree,
    history: createMemoryHistory({ initialEntries: [ruta] }),
  })
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}
afterEach(() => vi.unstubAllGlobals())

describe('diffs', () => {
  it('la lista muestra base → nueva y los casos con cambios sobre el total', async () => {
    montar('/proyectos/predicts/diffs')
    expect(await screen.findByRole('link', { name: 'master → pr-7' })).toBeInTheDocument()
    expect(screen.getByText('1 de 2')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Nuevo diff/ })).toBeInTheDocument()
  })

  it('el detalle clasifica los cambios por tipo, con el estado en rojo o verde', async () => {
    montar('/proyectos/predicts/diffs/diff-1')
    const paso = await screen.findByText('Paso s1')
    const li = paso.closest('li')!
    for (const t of ['Red', 'Texto', 'Visual', 'Consola']) expect(within(li).getByText(t)).toBeInTheDocument()
    expect(within(li).getByText('200').className).toContain('emerald')
    expect(within(li).getByText('500').className).toContain('destructive')
    expect(within(li).getByLabelText('Texto antes')).toHaveTextContent('Hola')
    expect(within(li).getByLabelText('Texto después')).toHaveTextContent('Adiós')
    // los casos con cambios van primero
    const titulos = screen.getAllByText(/^TC00/).map((e) => e.textContent)
    expect(titulos[0]).toContain('TC001')
  })

  it('el deslizador cambia entre las dos capturas', async () => {
    montar('/proyectos/predicts/diffs/diff-1')
    const rango = await screen.findByRole('slider', {
      name: 'Deslizador antes/después',
    })
    const despues = screen.getByAltText('Captura después')
    expect(despues.getAttribute('src')).toBe('/api/diffs/diff-1/capturas/TC001/s1-despues.png')
    expect(despues.style.clipPath).toBe('inset(0 0 0 50%)')
    fireEvent.change(rango, { target: { value: '0' } }) // todo «después»
    expect(despues.style.clipPath).toBe('inset(0 0 0 0%)')
    fireEvent.change(rango, { target: { value: '100' } }) // todo «antes»
    expect(despues.style.clipPath).toBe('inset(0 0 0 100%)')
  })
})
