import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, createRootRoute, createRoute, createRouter, RouterProvider } from '@tanstack/react-router'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { PestanasEstado } from '@/components/comun/Estado'
import { SidebarProvider } from '@/components/ui/sidebar'
import { TooltipProvider } from '@/components/ui/tooltip'
import { routeTree } from '@/routeTree.gen'
import { BarraGlobal } from './BarraGlobal'
import { EncabezadoPagina, type SlugPantalla } from './EncabezadoPagina'
import { SelectorTema } from './SelectorTema'

/** Monta `contenido` dentro de un router mínimo (los `Link` lo necesitan). */
async function montar(contenido: ReactNode, inicial = '/') {
  const raiz = createRootRoute({
    component: () => (
      <TooltipProvider>
        <SidebarProvider>{contenido}</SidebarProvider>
      </TooltipProvider>
    ),
  })
  const rutas = ['/', '/x', '/proyectos', '/suites', '/programaciones', '/ayuda'].map((path) =>
    createRoute({ getParentRoute: () => raiz, path }),
  )
  const router = createRouter({
    routeTree: raiz.addChildren(rutas),
    history: createMemoryHistory({ initialEntries: [inicial] }),
  })
  render(<RouterProvider router={router} />)
  return router
}

/** El panel entero (rutas reales) en `inicial`. */
function montarPanel(inicial: string) {
  const router = createRouter({ routeTree, history: createMemoryHistory({ initialEntries: [inicial] }) })
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return router
}

beforeEach(() => {
  localStorage.clear()
  document.documentElement.classList.remove('dark')
  vi.stubGlobal('fetch', async (entrada: Request | string) => {
    const url = new URL(typeof entrada === 'string' ? entrada : entrada.url, 'http://x')
    const json = (d: unknown) => new Response(JSON.stringify(d), { headers: { 'content-type': 'application/json' } })
    if (url.pathname === '/api/ejecuciones') return json([])
    if (url.pathname === '/api/etiquetas' || url.pathname === '/api/filtros') return json({})
    return new Response('no', { status: 404 })
  })
})
afterEach(() => vi.unstubAllGlobals())

describe('layout', () => {
  it('la barra global tiene Inicio, Proyectos, Suites, Programaciones y Ayuda', async () => {
    await montar(<BarraGlobal />)
    const enlaces = await screen.findAllByRole('link')
    expect(enlaces.map((e) => e.textContent)).toEqual(['Inicio', 'Proyectos', 'Suites', 'Programaciones', 'Ayuda'])
  })

  it('EncabezadoPagina: título serif, subtítulo, acciones y el ⓘ de ayuda', async () => {
    await montar(
      <EncabezadoPagina
        titulo="Corridas"
        subtitulo="Todas las corridas."
        ayuda={'corridas' satisfies SlugPantalla}
        acciones={<button>Nueva</button>}
      />,
    )
    expect(await screen.findByRole('heading', { name: 'Corridas' })).toHaveClass('font-serif')
    expect(screen.getByText('Todas las corridas.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Nueva' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Ayuda de esta pantalla' })).toHaveAttribute('href', '/ayuda?pantalla=corridas')
  })

  it('EncabezadoPagina sin ayuda no muestra el ⓘ', async () => {
    await montar(<EncabezadoPagina titulo="Corridas" />)
    await screen.findByRole('heading', { name: 'Corridas' })
    expect(screen.queryByRole('link', { name: 'Ayuda de esta pantalla' })).toBeNull()
  })

  it('el selector de tema alterna la clase dark y la recuerda; el claro es el predeterminado', async () => {
    const user = userEvent.setup()
    await montar(<SelectorTema />)
    await user.click(await screen.findByRole('button', { name: 'Cambiar a tema oscuro' }))
    expect(document.documentElement).toHaveClass('dark')
    expect(localStorage.getItem('dogfood.tema')).toBe('oscuro')
    await user.click(screen.getByRole('button'))
    expect(document.documentElement).not.toHaveClass('dark')
    expect(localStorage.getItem('dogfood.tema')).toBe('claro')
  })

  it('arranca con el tema guardado', async () => {
    localStorage.setItem('dogfood.tema', 'oscuro')
    await montar(<SelectorTema />)
    expect(await screen.findByRole('button', { name: 'Cambiar a tema claro' })).toBeInTheDocument()
  })
})

describe('navegación en dos niveles', () => {
  it('en /proyectos/predicts/casos se ven las dos barras y las migas «predicts › Casos de prueba»', async () => {
    montarPanel('/proyectos/predicts/casos')
    expect(await screen.findByRole('navigation', { name: 'Principal' })).toBeInTheDocument()
    const proyecto = screen.getByRole('navigation', { name: 'Proyecto' })
    expect(within(proyecto).getByRole('link', { name: /Casos de prueba/ })).toHaveAttribute('aria-current', 'page')
    expect(within(proyecto).getByRole('link', { name: /Insights/ })).toHaveAttribute('href', '/proyectos/predicts/insights')
    const migas = within(screen.getByRole('navigation', { name: 'Ruta' })).getAllByRole('listitem')
    expect(migas.map((m) => m.textContent).filter(Boolean)).toEqual(['predicts', 'Casos de prueba'])
    expect(await screen.findByRole('heading', { level: 1, name: 'Casos de prueba' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Compartir' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Copiar link' })).toBeInTheDocument()
  })

  it('«← Volver» lleva a /proyectos', async () => {
    const router = montarPanel('/proyectos/predicts/casos')
    await userEvent.setup().click(await screen.findByRole('link', { name: 'Volver' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/proyectos'))
    expect(await screen.findByRole('heading', { level: 1, name: 'Proyectos' })).toBeInTheDocument()
    expect(screen.queryByRole('navigation', { name: 'Proyecto' })).toBeNull()
  })

  it('«Compartir» copia el link público de dogfood.knaimero.app', async () => {
    const user = userEvent.setup()
    const escribir = vi.spyOn(navigator.clipboard, 'writeText')
    montarPanel('/proyectos/predicts/casos?estado=fallo')
    await user.click(await screen.findByRole('button', { name: 'Compartir' }))
    expect(escribir).toHaveBeenCalledWith('https://dogfood.knaimero.app/proyectos/predicts/casos?estado=fallo')
  })

  it.each([
    ['/corridas/c1', '/proyectos/predicts/corridas/c1'],
    ['/ejecuciones/e1', '/proyectos/predicts/ejecuciones/e1'],
    ['/casos', '/proyectos/predicts/casos'],
    ['/recorridos', '/proyectos/predicts/recorridos'],
    ['/dispositivos', '/proyectos/predicts/dispositivos'],
    ['/vista', '/proyectos/predicts/vista'],
    ['/proyectos/predicts', '/proyectos/predicts/casos'],
  ])('la ruta vieja %s redirige a %s', async (vieja, nueva) => {
    const router = createRouter({ routeTree, history: createMemoryHistory({ initialEntries: [vieja] }) })
    await router.load()
    expect(router.state.location.pathname).toBe(nueva)
  })

  it('PestanasEstado muestra los conteos y cambia el filtro en la URL', async () => {
    const user = userEvent.setup()
    const router = await montar(<PestanasEstado conteos={{ paso: 2, fallo: 17 }} />, '/x')
    expect(await screen.findByRole('tab', { name: /Todos\s*19/ })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: /Pasaron\s*2/ })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Bloqueados\s*0/ })).toBeInTheDocument()
    await user.click(screen.getByRole('tab', { name: /Fallaron\s*17/ }))
    await waitFor(() => expect(router.state.location.search).toEqual({ estado: 'fallo' }))
    expect(router.state.location.href).toBe('/x?estado=fallo')
    expect(screen.getByRole('tab', { name: /Fallaron/ })).toHaveAttribute('aria-selected', 'true')
  })
})
