import { createMemoryHistory, createRootRoute, createRoute, createRouter, RouterProvider } from '@tanstack/react-router'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { ReactNode } from 'react'
import { beforeEach, describe, expect, it } from 'vitest'

import { SidebarProvider } from '@/components/ui/sidebar'
import { TooltipProvider } from '@/components/ui/tooltip'
import { BarraLateral } from './BarraLateral'
import { PageHeader, type SlugPantalla } from './PageHeader'
import { SelectorTema } from './SelectorTema'

/** Monta `contenido` dentro de un router mínimo (los `Link` lo necesitan). */
async function montar(contenido: ReactNode) {
  const raiz = createRootRoute({ component: () => (
      <TooltipProvider>
        <SidebarProvider>{contenido}</SidebarProvider>
      </TooltipProvider>
    ) })
  const rutas = ['/', '/recorridos', '/dispositivos', '/vista', '/ayuda'].map((path) =>
    createRoute({ getParentRoute: () => raiz, path }),
  )
  const router = createRouter({
    routeTree: raiz.addChildren(rutas),
    history: createMemoryHistory({ initialEntries: ['/'] }),
  })
  render(<RouterProvider router={router} />)
}

beforeEach(() => {
  localStorage.clear()
  document.documentElement.classList.remove('dark')
})

describe('layout', () => {
  it('la barra lateral tiene los 5 enlaces', async () => {
    await montar(<BarraLateral />)
    const enlaces = await screen.findAllByRole('link')
    expect(enlaces.map((e) => e.textContent)).toEqual([
      'Corridas',
      'Recorridos',
      'Dispositivos',
      'Vista en vivo',
      'Ayuda',
    ])
  })

  it('PageHeader con ayuda muestra el ⓘ con link a la ayuda de la pantalla', async () => {
    await montar(<PageHeader titulo="Corridas" ayuda={'corridas' satisfies SlugPantalla} />)
    const link = await screen.findByRole('link', { name: 'Ayuda de esta pantalla' })
    expect(link).toHaveAttribute('href', '/ayuda?pantalla=corridas')
  })

  it('PageHeader sin ayuda no muestra el ⓘ', async () => {
    await montar(<PageHeader titulo="Corridas" />)
    await screen.findByRole('heading', { name: 'Corridas' })
    expect(screen.queryByRole('link', { name: 'Ayuda de esta pantalla' })).toBeNull()
  })

  it('el selector de tema alterna la clase dark y la recuerda', async () => {
    const user = userEvent.setup()
    await montar(<SelectorTema />)
    await user.click(await screen.findByRole('button'))
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
