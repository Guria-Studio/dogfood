import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, createRootRoute, createRoute, createRouter, RouterProvider } from '@tanstack/react-router'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { General, Notificaciones } from './Paginas'

const proyecto = {
  slug: 'predicts', nombre: 'Predicts', tipo: 'web', instrucciones: '', entornos: [],
  acceso: { usuario: '', secreto_ref: '' },
  comportamiento: { login_una_vez: false, viewport: 'escritorio', concurrencia: null },
  notificaciones: { slack: true, issues_github: true, repo: '', etiqueta: '', comentar_pr: false },
}

let llamadas: { metodo: string; ruta: string; cuerpo: string }[] = []
function montar(Pagina: (p: { slug: string }) => React.ReactNode) {
  llamadas = []
  vi.stubGlobal('fetch', async (entrada: Request | URL | string, init?: RequestInit) => {
    const url = new URL(String(entrada instanceof Request ? entrada.url : entrada), 'http://x')
    const metodo = init?.method ?? 'GET'
    if (metodo !== 'GET') llamadas.push({ metodo, ruta: url.pathname, cuerpo: String(init?.body ?? '') })
    return new Response(JSON.stringify(proyecto), { headers: { 'content-type': 'application/json' } })
  })
  const raiz = createRootRoute()
  const hija = (path: string, component: () => React.ReactNode) => createRoute({ getParentRoute: () => raiz, path, component })
  const router = createRouter({
    routeTree: raiz.addChildren([hija('/p', () => <Pagina slug="predicts" />), hija('/proyectos', () => <p>lista de proyectos</p>)]),
    history: createMemoryHistory({ initialEntries: ['/p'] }),
  })
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
}
afterEach(() => vi.unstubAllGlobals())

describe('ajustes del proyecto', () => {
  it('«Guardar cambios» está deshabilitado sin cambios y guarda al editar', async () => {
    montar(General)
    const guardar = await screen.findByRole('button', { name: 'Guardar cambios' })
    expect(guardar).toBeDisabled()
    await userEvent.type(screen.getByLabelText(/^Instrucciones/), 'Enfócate en el checkout')
    expect(guardar).toBeEnabled()
    await userEvent.click(guardar)
    await waitFor(() => expect(llamadas).toHaveLength(1))
    expect(llamadas[0].metodo).toBe('PATCH')
    expect(JSON.parse(llamadas[0].cuerpo).instrucciones).toBe('Enfócate en el checkout')
    expect(await screen.findByText('Cambios guardados')).toBeInTheDocument()
  })

  it('el tipo es de solo lectura', async () => {
    montar(General)
    expect(await screen.findByLabelText(/^Tipo/)).toBeDisabled()
    expect(screen.getByText(/no se puede cambiar después de crear/)).toBeInTheDocument()
  })

  it('borrar exige escribir el nombre del proyecto', async () => {
    montar(General)
    const borrar = await screen.findByRole('button', { name: 'Borrar proyecto' })
    expect(borrar).toBeDisabled()
    await userEvent.type(screen.getByLabelText(/Escribe/), 'Predic')
    expect(borrar).toBeDisabled()
    await userEvent.type(screen.getByLabelText(/Escribe/), 'ts')
    expect(borrar).toBeEnabled()
    await userEvent.click(borrar)
    await waitFor(() => expect(llamadas[0]).toMatchObject({ metodo: 'DELETE', ruta: '/api/proyectos/predicts' }))
    expect(JSON.parse(llamadas[0].cuerpo)).toEqual({ confirmar: 'predicts' })
  })

  it('el webhook de Slack se envía pero nunca se muestra', async () => {
    montar(Notificaciones)
    const campo = await screen.findByLabelText(/^Webhook de Slack/)
    expect(campo).toHaveValue('')
    await userEvent.type(campo, 'https://hooks.slack.com/services/T/B/x')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar cambios' }))
    await waitFor(() => expect(llamadas).toHaveLength(1))
    expect(JSON.parse(llamadas[0].cuerpo).notificaciones.slack_webhook).toMatch(/^https:/)
    await waitFor(() => expect(screen.getByLabelText(/^Webhook de Slack/)).toHaveValue(''))
  })
})
