import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { Programaciones } from './Programaciones'
import { Suites } from './Suites'

const json = (d: unknown) => new Response(JSON.stringify(d), { headers: { 'content-type': 'application/json' } })
let escrituras: { metodo: string; ruta: string; cuerpo: string }[] = []

function montar(Pagina: () => React.ReactNode, datos: Record<string, unknown>) {
  escrituras = []
  vi.stubGlobal('fetch', async (entrada: Request | URL | string, init?: RequestInit) => {
    const ruta = new URL(String(entrada instanceof Request ? entrada.url : entrada), 'http://x').pathname
    const metodo = init?.method ?? 'GET'
    if (metodo !== 'GET') escrituras.push({ metodo, ruta, cuerpo: String(init?.body ?? '') })
    return json(datos[ruta] ?? {})
  })
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <Pagina />
    </QueryClientProvider>,
  )
}
afterEach(() => vi.unstubAllGlobals())

const grupo = (c: { id: string; nombre: string }) => ({ grupos: [{ caso_de_uso: 'x', casos: [c] }] })

describe('suites', () => {
  it('muestra «Advertencia» con resultados mixtos', async () => {
    montar(Suites, {
      '/api/suites': [{ id: 1, nombre: 'Humo', casos: [], n_casos: 3, ultima_ejecucion: null, estado: 'advertencia' }],
    })
    expect(await screen.findByText('Advertencia')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Correr suite/ })).toBeInTheDocument()
  })

  it('crea una suite con casos de dos proyectos y la corre', async () => {
    montar(Suites, {
      '/api/suites': [{ id: 7, nombre: 'Humo', casos: [], n_casos: 2, ultima_ejecucion: null, estado: null }],
      '/api/proyectos': [{ slug: 'predicts' }, { slug: 'otra' }],
      '/api/proyectos/predicts/casos': grupo({ id: 'a:p1', nombre: 'Registro' }),
      '/api/proyectos/otra/casos': grupo({ id: 'b:p2', nombre: 'Login' }),
    })
    await userEvent.click(await screen.findByRole('button', { name: /Nueva suite/ }))
    await userEvent.type(screen.getByLabelText('Nombre de la suite'), 'Previa')
    await userEvent.click(await screen.findByLabelText('Registro'))
    await userEvent.click(screen.getByLabelText('Login'))
    await userEvent.click(screen.getByRole('button', { name: 'Crear suite' }))
    await waitFor(() => expect(escrituras).toHaveLength(1))
    expect(JSON.parse(escrituras[0].cuerpo).casos).toEqual([
      { proyecto: 'predicts', caso: 'a:p1' },
      { proyecto: 'otra', caso: 'b:p2' },
    ])
    await userEvent.click(await screen.findByRole('button', { name: /Correr suite/ }))
    await waitFor(() => expect(escrituras.at(-1)).toMatchObject({ metodo: 'POST', ruta: '/api/suites/7/correr' }))
  })
})

describe('programaciones', () => {
  it('sin programaciones explica con tres beneficios', async () => {
    montar(Programaciones, { '/api/programaciones': [] })
    expect(await screen.findByText('Corridas sin pedirlas')).toBeInTheDocument()
    expect(screen.getByText('Calidad en el tiempo')).toBeInTheDocument()
    expect(screen.getByText('Regresiones encontradas de noche')).toBeInTheDocument()
  })

  it('crea y borra una programación', async () => {
    montar(Programaciones, {
      '/api/programaciones': [{ id: 3, suite_id: 7, suite: 'Humo', frecuencia: 'dia', hora: '03:00', dia: '', cron: '', slack: true, calendario: '' }],
      '/api/suites': [{ id: 7, nombre: 'Humo', casos: [], n_casos: 1, ultima_ejecucion: null, estado: null }],
    })
    await userEvent.click(await screen.findByRole('button', { name: 'Borrar programación de Humo' }))
    await waitFor(() => expect(escrituras[0]).toMatchObject({ metodo: 'DELETE', ruta: '/api/programaciones/3' }))
    await userEvent.click(screen.getByRole('button', { name: /Nueva programación/ }))
    await userEvent.selectOptions(await screen.findByLabelText('Suite'), '7')
    await userEvent.click(screen.getByRole('button', { name: 'Crear programación' }))
    await waitFor(() => expect(escrituras[1]).toMatchObject({ metodo: 'POST', ruta: '/api/programaciones' }))
    expect(JSON.parse(escrituras[1].cuerpo)).toMatchObject({ suite_id: 7, frecuencia: 'dia', hora: '03:00' })
  })
})
