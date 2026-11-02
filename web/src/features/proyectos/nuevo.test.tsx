import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, createRootRoute, createRoute, createRouter, RouterProvider } from '@tanstack/react-router'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { ListaProyectos } from './ListaProyectos'
import { NuevoProyecto } from './NuevoProyecto'

const lista = [
  { slug: 'predicts', nombre: 'predicts', tipo: 'web' },
  { slug: 'mobile-mao', nombre: 'mobile-mao', tipo: 'android' },
].map((p) => ({
  ...p, creado: '2026-01-01T00:00:00Z',
  notificaciones: { slack: false, issues_github: true, repo: '' },
  ultimos: { corrida_id: 'c1', pasaron: 2, fallaron: 1, ultima_actividad: '2026-02-01T00:00:00Z' },
}))

let enviados: { url: string; cuerpo: string }[] = []
function montar(inicial: string) {
  enviados = []
  vi.stubGlobal('fetch', async (entrada: Request | URL | string, init?: RequestInit) => {
    const url = new URL(String(entrada instanceof Request ? entrada.url : entrada), 'http://x')
    if (init?.method === 'POST') {
      enviados.push({ url: url.pathname, cuerpo: String(init.body) })
      return new Response('{}', { status: 201, headers: { 'content-type': 'application/json' } })
    }
    return new Response(JSON.stringify(lista), { headers: { 'content-type': 'application/json' } })
  })
  const raiz = createRootRoute()
  const hija = (path: string, component?: () => React.ReactNode) => createRoute({ getParentRoute: () => raiz, path, component })
  const router = createRouter({
    routeTree: raiz.addChildren([
      hija('/proyectos', ListaProyectos),
      hija('/proyectos/nuevo', NuevoProyecto),
      hija('/proyectos/$proyecto/casos', () => <p>casos del proyecto</p>),
    ]),
    history: createMemoryHistory({ initialEntries: [inicial] }),
  })
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return router
}
afterEach(() => vi.unstubAllGlobals())

async function basico() {
  await userEvent.type(await screen.findByLabelText('URL'), 'https://mi-app.com')
  await userEvent.type(screen.getByLabelText('Nombre'), 'Mi app')
}

describe('asistente de proyecto nuevo', () => {
  it('no avanza sin URL válida', async () => {
    montar('/proyectos/nuevo')
    await userEvent.type(await screen.findByLabelText('Nombre'), 'Mi app')
    await userEvent.type(screen.getByLabelText('URL'), 'no-es-url')
    expect(screen.getByRole('button', { name: 'Siguiente' })).toBeDisabled()
    await userEvent.clear(screen.getByLabelText('URL'))
    await userEvent.type(screen.getByLabelText('URL'), 'https://mi-app.com')
    expect(screen.getByRole('button', { name: 'Siguiente' })).toBeEnabled()
  })

  it('no muestra la contraseña después de guardarla', async () => {
    montar('/proyectos/nuevo')
    await basico()
    await userEvent.click(screen.getByRole('button', { name: 'Siguiente' }))
    await userEvent.click(screen.getByLabelText('Con un usuario de prueba'))
    await userEvent.type(screen.getByLabelText('Contraseña'), 'secreto-123')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    expect(screen.getByText('Contraseña guardada como secreto')).toBeInTheDocument()
    expect(screen.queryByLabelText('Contraseña')).toBeNull()
    expect(document.body.innerHTML).not.toContain('secreto-123')
  })

  it('un proyecto no web, al terminar, navega a sus casos', async () => {
    const router = montar('/proyectos/nuevo')
    await userEvent.click(await screen.findByLabelText('Android'))
    await userEvent.type(screen.getByLabelText('Objetivo (paquete o bundle id)'), 'com.mi.app')
    await userEvent.type(screen.getByLabelText('Nombre'), 'Mi app')
    await userEvent.click(screen.getByRole('button', { name: 'Siguiente' }))
    await userEvent.click(screen.getByRole('button', { name: 'Siguiente' }))
    await userEvent.click(screen.getByRole('button', { name: 'Crear proyecto' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/proyectos/mi-app/casos'))
    expect(enviados[0].url).toBe('/api/proyectos')
    expect(JSON.parse(enviados[0].cuerpo)).toMatchObject({ slug: 'mi-app', tipo: 'android' })
  })
})

describe('lista de proyectos', () => {
  it('las pestañas de tipo filtran la tabla', async () => {
    montar('/proyectos')
    await screen.findByText('mobile-mao')
    expect(document.querySelectorAll('[data-proyecto]')).toHaveLength(2)
    await userEvent.click(screen.getByRole('tab', { name: 'Android' }))
    expect(document.querySelectorAll('[data-proyecto]')).toHaveLength(1)
    expect(screen.queryByText('predicts')).toBeNull()
    await userEvent.click(screen.getByRole('tab', { name: 'Web' }))
    expect(document.querySelector('[data-proyecto="predicts"]')).not.toBeNull()
  })
})
