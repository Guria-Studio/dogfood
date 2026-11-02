import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { EscenarioProyecto } from './api'
import { RevisarPlan } from './RevisarPlan'

const json = (d: unknown, status = 200) => new Response(JSON.stringify(d), { status, headers: { 'content-type': 'application/json' } })
const base = (id: string): EscenarioProyecto => ({
  id, titulo: `Escenario ${id}`, objetivo: `Objetivo ${id}`, criterio_exito: 'c', superficies: ['/perfil'], prioridad: 'media', estado: 'borrador',
})
let filas: EscenarioProyecto[]
let patches: { id: string; cuerpo: Record<string, unknown> }[]

beforeEach(() => {
  filas = [base('a'), base('b'), base('c')]
  patches = []
  vi.stubGlobal('fetch', async (entrada: Request | URL | string, init?: RequestInit) => {
    const u = new URL(String(entrada instanceof Request ? entrada.url : entrada), 'http://x')
    if (u.pathname === '/api/proyectos/web1/mapa') return json({ id: 'X', creado: '', pantallas: [{ path: '/perfil', url: '', titulo: 'Perfil', acciones: [], captura: null }], funcionalidades: [] })
    if (init?.method === 'PATCH') {
      const id = decodeURIComponent(u.pathname.split('/').pop()!)
      const cuerpo = JSON.parse(String(init.body))
      patches.push({ id, cuerpo })
      const i = filas.findIndex((f) => f.id === id)
      filas[i] = { ...filas[i], ...cuerpo }
      return json(filas[i])
    }
    const estado = u.searchParams.get('estado')
    return json(filas.filter((f) => !estado || f.estado === estado))
  })
})
afterEach(() => vi.unstubAllGlobals())

function montar() {
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RevisarPlan slug="web1" />
    </QueryClientProvider>,
  )
}
const abrir = async () => {
  expect(await screen.findByText('3 escenarios propuestos para revisar')).toBeInTheDocument()
  await userEvent.click(screen.getByRole('button', { name: 'Revisar plan' }))
}

describe('revisar el plan', () => {
  it('sin borradores no aparece la franja', async () => {
    filas = []
    montar()
    await waitFor(() => expect(screen.queryByText(/para revisar/)).toBeNull())
  })

  it('aceptar 2 de 3 deja 2 aceptados y 1 borrador', async () => {
    montar()
    await abrir()
    await userEvent.click(screen.getByLabelText('Elegir Escenario a'))
    await userEvent.click(screen.getByLabelText('Elegir Escenario c'))
    await userEvent.click(screen.getByRole('button', { name: 'Aceptar seleccionados' }))
    await waitFor(() => expect(filas.filter((f) => f.estado === 'aceptado').map((f) => f.id)).toEqual(['a', 'c']))
    expect(filas.filter((f) => f.estado === 'borrador')).toHaveLength(1)
    expect(await screen.findByText('1 escenario propuesto para revisar')).toBeInTheDocument()
  })

  it('editar el objetivo en línea se guarda', async () => {
    montar()
    await abrir()
    const campo = screen.getByLabelText('Objetivo de Escenario b')
    await userEvent.clear(campo)
    await userEvent.type(campo, 'Otro objetivo')
    await userEvent.tab()
    await waitFor(() => expect(patches).toEqual([{ id: 'b', cuerpo: { objetivo: 'Otro objetivo' } }]))
  })

  it('la prioridad es editable y Ver flujo muestra las pantallas', async () => {
    montar()
    await abrir()
    await userEvent.selectOptions(screen.getByLabelText('Prioridad de Escenario a'), 'alta')
    await waitFor(() => expect(patches[0]).toEqual({ id: 'a', cuerpo: { prioridad: 'alta' } }))
    const fila = document.querySelector('[data-escenario="a"]') as HTMLElement
    await userEvent.click(within(fila).getByRole('button', { name: 'Ver flujo' }))
    expect(within(screen.getByLabelText('Flujo de Escenario a')).getByText('/perfil')).toBeInTheDocument()
  })
})
