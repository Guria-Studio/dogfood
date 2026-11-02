import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, createRootRoute, createRoute, createRouter, RouterProvider } from '@tanstack/react-router'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { NuevoProyecto } from '@/features/proyectos/NuevoProyecto'
import { Mapa } from './Mapa'

const json = (d: unknown, status = 200) => new Response(JSON.stringify(d), { status, headers: { 'content-type': 'application/json' } })
const mapa = {
  id: 'X1', creado: '2026-01-01T00:00:00Z',
  pantallas: [
    { path: '/', url: 'http://x/', titulo: 'Inicio', acciones: [], captura: '/tmp/a.png' },
    { path: '/perfil', url: 'http://x/perfil', titulo: 'Perfil', acciones: [], captura: null },
  ],
  funcionalidades: [
    { nombre: 'Cuenta', casos: [
      { id: 'editar-perfil', nombre: 'Editar perfil', pantallas: ['/perfil'], estado: 'visto' },
      { id: 'borrar-cuenta', nombre: 'Exportar datos', pantallas: [], estado: 'solo_prd' },
    ] },
    { nombre: 'Catálogo', casos: [{ id: 'ver-productos', nombre: 'Ver productos', pantallas: ['/'], estado: 'visto' }] },
  ],
}

let llamadas: { metodo: string; ruta: string; cuerpo: string }[] = []
let respuestas: string[] = []
function falso(extra?: (ruta: string, init?: RequestInit) => Response | undefined) {
  llamadas = []
  respuestas = []
  vi.stubGlobal('fetch', async (entrada: Request | URL | string, init?: RequestInit) => {
    const u = new URL(String(entrada instanceof Request ? entrada.url : entrada), 'http://x')
    llamadas.push({ metodo: init?.method ?? 'GET', ruta: u.pathname, cuerpo: String(init?.body ?? '') })
    const r = extra?.(u.pathname, init)
    if (r) { respuestas.push(await r.clone().text()); return r }
    if (u.pathname === '/api/proyectos/web1/mapa') return json(mapa)
    if (u.pathname === '/api/proyectos/web1/exploraciones') return json({ id: 'X-1' })
    if (u.pathname === '/api/corridas/X-1/estado') return json({ id: 'X-1', estado: 'activa', corrida_id: null, terminados: 0, total: 0, en_curso: [], log: ['pantalla /perfil'] })
    return json({ ok: true }, 201)
  })
}
afterEach(() => vi.unstubAllGlobals())

function montar(inicial: string) {
  const raiz = createRootRoute()
  const hija = (path: string, component: () => React.ReactNode) => createRoute({ getParentRoute: () => raiz, path, component })
  const router = createRouter({
    routeTree: raiz.addChildren([
      hija('/proyectos/nuevo', NuevoProyecto),
      hija('/proyectos/$proyecto/mapa', () => <Mapa />),
      hija('/proyectos/$proyecto/casos', () => <p>casos</p>),
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

describe('mapa', () => {
  it('muestra las funcionalidades y marca en ámbar lo de solo_prd', async () => {
    falso()
    montar('/proyectos/web1/mapa')
    expect(await screen.findByText('Cuenta')).toBeInTheDocument()
    expect(screen.getByText('Catálogo')).toBeInTheDocument()
    const brecha = document.querySelector('[data-estado="solo_prd"]')!
    expect(brecha).toHaveTextContent('Exportar datos')
    expect(brecha.querySelector('.bg-amber-100')).toHaveTextContent('posible brecha')
    expect(document.querySelector('[data-estado="visto"] .bg-amber-100')).toBeNull()
    expect(document.querySelector('[data-pantalla="/"] img')).not.toBeNull() // miniatura con captura
  })

  it('Explorar de nuevo lanza la exploración y muestra el progreso', async () => {
    falso()
    montar('/proyectos/web1/mapa')
    await userEvent.click(await screen.findByRole('button', { name: 'Explorar de nuevo' }))
    expect(await screen.findByText('Explorando la app…')).toBeInTheDocument()
    expect(llamadas.some((l) => l.metodo === 'POST' && l.ruta === '/api/proyectos/web1/exploraciones')).toBe(true)
  })
})

describe('asistente de proyecto web', () => {
  it('crea el proyecto web, guarda la contraseña sin devolverla y ofrece explorar', async () => {
    falso((ruta, init) => (init?.method === 'POST' && ruta === '/api/proyectos' ? json({ slug: 'web1' }, 201) : undefined))
    const router = montar('/proyectos/nuevo')
    await userEvent.type(await screen.findByLabelText('URL'), 'https://app.mi-empresa.com')
    expect(screen.getByRole('alert')).toHaveTextContent('parece de producción')
    await userEvent.clear(screen.getByLabelText('URL'))
    await userEvent.type(screen.getByLabelText('URL'), 'http://localhost:3000')
    expect(screen.queryByText(/parece de producción/)).toBeNull()
    await userEvent.type(screen.getByLabelText('Nombre'), 'Web1')
    await userEvent.click(screen.getByRole('button', { name: 'Siguiente' }))
    await userEvent.click(screen.getByLabelText('Con un usuario de prueba'))
    await userEvent.type(screen.getByLabelText('Usuario'), 'ana@x.com')
    await userEvent.type(screen.getByLabelText('Contraseña'), 'secreto-123')
    await userEvent.click(screen.getByRole('button', { name: 'Guardar' }))
    await userEvent.click(screen.getByRole('button', { name: 'Siguiente' }))
    await userEvent.type(screen.getByLabelText('Levantar (comando)'), 'docker compose up -d')
    await userEvent.click(screen.getByRole('button', { name: 'Crear proyecto' }))

    await userEvent.click(await screen.findByRole('button', { name: 'Explorar la app' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/proyectos/web1/mapa'))

    const crear = llamadas.find((l) => l.metodo === 'POST' && l.ruta === '/api/proyectos')!
    const cuerpo = JSON.parse(crear.cuerpo)
    expect(cuerpo).toMatchObject({ slug: 'web1', tipo: 'web', objetivo: 'web', levantar: 'docker compose up -d', acceso: { modo: 'usuario_prueba', usuario: 'ana@x.com' } })
    expect(crear.cuerpo).not.toContain('secreto-123') // la contraseña no viaja en el proyecto
    const secreto = llamadas.find((l) => l.metodo === 'PUT' && l.ruta === '/api/proyectos/web1/secreto')!
    expect(JSON.parse(secreto.cuerpo)).toEqual({ valor: 'secreto-123' })
    expect(respuestas.join('')).not.toContain('secreto-123') // ninguna respuesta la devuelve
    expect(document.body.innerHTML).not.toContain('secreto-123')
  })
})
