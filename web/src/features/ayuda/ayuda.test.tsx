import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { createMemoryHistory, createRouter, RouterProvider } from '@tanstack/react-router'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { routeTree } from '@/routeTree.gen'

const doc = (slug: string, titulo: string, seccion: string, pantallas: string[] = []) => ({
  slug, titulo, seccion, orden: 1, pantallas,
})
const DOCS = [
  doc('como-funciona', 'Cómo funciona dogfood', 'empezar', ['corridas']),
  doc('primera-corrida', 'Tu primera corrida', 'empezar'),
  doc('leer-una-ejecucion', 'Leer una ejecución', 'guias', ['ejecucion']),
  doc('glosario', 'Glosario', 'referencia'),
]
const NUMS = [1, 2, 3, 4, 5, 6]
const PASOS = NUMS
  .map((n) => `## Paso ${n}. Título ${n}\n\n- **Qué hace:** Hace la cosa ${n}. Y más.\n`)
  .join('\n')
const MD: Record<string, string> = {
  'como-funciona': `# Cómo funciona\n\n${PASOS}`,
  'primera-corrida': [
    '# Primera', '', '## Tabla', '', '| a | b |', '|---|---|', '| 1 | 2 |', '', '## Código', '',
    '```bash', 'uv run dogfood run', '```', '', 'Ver [x](glosario.md).',
  ].join('\n'),
}

let fetchFalso: ReturnType<typeof vi.fn>
beforeEach(() => {
  fetchFalso = vi.fn(async (entrada: RequestInfo | URL) => {
    const url = new URL(String(entrada instanceof Request ? entrada.url : entrada), 'http://x')
    let cuerpo: unknown
    if (url.pathname === '/api/ayuda') {
      const p = url.searchParams.get('pantalla')
      cuerpo = DOCS.filter((d) => !p || d.pantallas.includes(p))
    } else if (url.pathname === '/api/ayuda/buscar') {
      cuerpo = [{ slug: 'glosario', titulo: 'Glosario', fragmento: 'un hallazgo es algo', puntaje: 3 }]
    } else {
      const slug = url.pathname.split('/').pop()!
      cuerpo = { doc: DOCS.find((d) => d.slug === slug), markdown: MD[slug] ?? `# ${slug}` }
    }
    return new Response(JSON.stringify(cuerpo), { headers: { 'content-type': 'application/json' } })
  })
  vi.stubGlobal('fetch', fetchFalso)
})
afterEach(() => vi.unstubAllGlobals())

function montar(ruta: string) {
  const router = createRouter({ routeTree, history: createMemoryHistory({ initialEntries: [ruta] }) })
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  )
  return router
}

describe('ayuda', () => {
  it('la portada muestra las 6 tarjetas y las tres secciones', async () => {
    montar('/ayuda')
    for (const n of NUMS) expect(await screen.findByText(`Título ${n}`)).toBeInTheDocument()
    for (const s of ['Empezar', 'Guías', 'Referencia']) expect(screen.getByRole('heading', { name: s })).toBeInTheDocument()
  })

  it('escribir en el buscador pide /api/ayuda/buscar una sola vez tras el debounce', async () => {
    montar('/ayuda')
    await userEvent.type(await screen.findByLabelText('Buscar en la ayuda'), 'hallazgo')
    expect(await screen.findByText('hallazgo', { selector: 'mark' })).toBeInTheDocument()
    const busquedas = fetchFalso.mock.calls.filter(([u]) => String(u).includes('/api/ayuda/buscar'))
    expect(busquedas).toHaveLength(1)
  })

  it('?pantalla=ejecucion muestra el bloque de ayuda de esa pantalla', async () => {
    montar('/ayuda?pantalla=ejecucion')
    const bloque = await screen.findByRole('region', { name: 'Ayuda para esta pantalla' })
    expect(bloque).toHaveTextContent('Leer una ejecución')
  })

  it('un documento renderiza tabla GFM, índice lateral y botón de copiar', async () => {
    montar('/ayuda/primera-corrida')
    expect(await screen.findByRole('table')).toBeInTheDocument()
    const indice = screen.getByRole('complementary', { name: 'En esta página' })
    expect(indice).toHaveTextContent('Tabla')
    expect(indice).toHaveTextContent('Código')
    expect(screen.getByRole('button', { name: 'Copiar código' })).toBeInTheDocument()
  })

  it('un link a glosario.md navega a /ayuda/glosario', async () => {
    const router = montar('/ayuda/primera-corrida')
    await userEvent.click(await screen.findByRole('link', { name: 'x' }))
    await waitFor(() => expect(router.state.location.pathname).toBe('/ayuda/glosario'))
  })
})
