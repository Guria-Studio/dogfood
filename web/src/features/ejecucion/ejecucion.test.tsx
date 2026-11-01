import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
  RouterProvider,
} from '@tanstack/react-router'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { Toaster } from '@/components/ui/sonner'
import { TooltipProvider } from '@/components/ui/tooltip'
import { DetalleEjecucion } from './DetalleEjecucion'

// openapi-fetch arma `new Request('/api/...')` y en Node una URL relativa no parsea: le damos
// la base de jsdom. Tiene que correr antes de importar el cliente (lo captura al crearse).
vi.hoisted(() => {
  const Original = globalThis.Request
  globalThis.Request = class extends Original {
    constructor(entrada: RequestInfo | URL, init?: RequestInit) {
      super(typeof entrada === 'string' ? new URL(entrada, 'http://localhost') : entrada, init)
    }
  }
})

const paso = (n: number, extra: object = {}) => ({
  n, url: `http://app/p${n}`, pantalla: `pantalla ${n}`, accion: `acción ${n}`, captura: null,
  razonamiento: `razono ${n}`, paso_contrato: '', esperado: `espero ${n}`, observado: `veo ${n}`,
  consola: [], red: [], ...extra,
})

const detalle = {
  ejecucion: {
    id: 'e1', persona_id: 'p1', escenario_id: 'login', modelo: 'sonnet', estado: 'terminada',
    driver: 'web', motor: 'api', backend: 'anthropic', resultado: 'fallo', duracion_s: 42,
    motivo_juez: 'no entró', notas: [],
  },
  corrida: {
    id: 'c1', objetivo: 'predicts', ref: 'main', commit: 'abc', version: 'v1',
    inicio: '2026-11-01T10:00:00', estado: 'terminada',
  },
  persona: {
    id: 'p1', nombre: 'Ana', empresa: 'X', rubro: 'y', idioma: 'es', destreza: 2, paciencia: 3,
    intencion: 'apostar', estilo: [],
  },
  pasos: [
    paso(1, { consola: [{ nivel: 'error', texto: 'boom', url: 'http://app/p1' }] }),
    paso(2, { red: [{ metodo: 'GET', url: 'http://app/api/x', estado: 500, ms: 12.3 }] }),
    paso(3),
  ],
  consola: [], red: [], fricciones: {}, video: null, trace: '/archivos/r/trace.zip', logcat: '',
}

type Pedido = { metodo: string; ruta: string; header: string | null }
let pedidos: Pedido[] = []
let respuestaIssue: Response

beforeEach(() => {
  pedidos = []
  respuestaIssue = Response.json({ url: 'https://github.com/o/r/issues/7', accion: 'creado', aviso: '' })
  vi.stubGlobal('fetch', async (req: Request) => {
    const url = new URL(req.url)
    pedidos.push({ metodo: req.method, ruta: url.pathname + url.search, header: req.headers.get('X-Dogfood') })
    if (url.pathname === '/api/ejecuciones/e1') return Response.json(detalle)
    if (url.pathname === '/api/ejecuciones/e1/issue') return respuestaIssue
    return new Response('no', { status: 404 })
  })
})
afterEach(() => vi.unstubAllGlobals())

async function montar() {
  const raiz = createRootRoute()
  const rutas = [
    createRoute({ getParentRoute: () => raiz, path: '/ejecuciones/$id', component: () => <DetalleEjecucion id="e1" /> }),
    createRoute({ getParentRoute: () => raiz, path: '/corridas/$id' }),
    createRoute({ getParentRoute: () => raiz, path: '/ayuda' }),
  ]
  const router = createRouter({
    routeTree: raiz.addChildren(rutas),
    history: createMemoryHistory({ initialEntries: ['/ejecuciones/e1'] }),
  })
  render(
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
      <TooltipProvider>
        <RouterProvider router={router} />
        <Toaster />
      </TooltipProvider>
    </QueryClientProvider>,
  )
  await screen.findByText('Paso 1 · pantalla 1')
}

const actual = () => within(screen.getByRole('navigation', { name: 'Línea de tiempo' })).getByRole('button', { current: 'step' })
const publicaciones = () => pedidos.filter((p) => p.metodo === 'POST')

describe('detalle de ejecución', () => {
  it('→ y ← cambian de paso y la línea de tiempo marca el actual', async () => {
    const user = userEvent.setup()
    await montar()
    expect(actual()).toHaveTextContent('1')
    await user.keyboard('{ArrowRight}')
    expect(screen.getByText('Paso 2 · pantalla 2')).toBeInTheDocument()
    expect(screen.getByText('razono 2')).toBeInTheDocument()
    expect(actual()).toHaveTextContent('2')
    await user.keyboard('{ArrowRight}{ArrowRight}') // no pasa del último
    expect(actual()).toHaveTextContent('3')
    await user.keyboard('{ArrowLeft}')
    expect(actual()).toHaveTextContent('2')
    await user.click(screen.getByRole('button', { name: 'Paso 1' }))
    expect(actual()).toHaveTextContent('1')
    await user.click(screen.getByRole('button', { name: /Siguiente/ }))
    expect(screen.getByText('espero 2')).toBeInTheDocument()
  })

  it('la consola y la red del paso aparecen en sus pestañas', async () => {
    const user = userEvent.setup()
    await montar()
    expect(screen.getByRole('tabpanel')).toHaveTextContent('[error] boom')
    await user.click(screen.getByRole('tab', { name: 'Red (0)' }))
    expect(screen.getByRole('tabpanel')).toHaveTextContent('Sin pedidos de red')
    await user.click(screen.getByRole('button', { name: 'Paso 2' }))
    await user.click(screen.getByRole('tab', { name: 'Red (1)' }))
    expect(screen.getByRole('tabpanel')).toHaveTextContent('GET http://app/api/x → 500 (12 ms)')
    expect(screen.getByText('uv run playwright show-trace trace.zip')).toBeInTheDocument()
  })

  it('«Crear issue» no publica sin confirmar; al confirmar manda el POST con el header y muestra el link', async () => {
    const user = userEvent.setup()
    await montar()
    await user.click(screen.getByRole('button', { name: 'Crear issue' }))
    const dialogo = await screen.findByRole('dialog')
    expect(dialogo).toHaveTextContent('login terminó en fallo')
    expect(dialogo).toHaveTextContent('repositorio de GitHub configurado')
    await user.click(within(dialogo).getByRole('button', { name: 'Cancelar' }))
    expect(publicaciones()).toEqual([])

    await user.click(screen.getByRole('button', { name: 'Crear issue' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Publicar' }))
    await waitFor(() => expect(publicaciones()).toHaveLength(1))
    expect(publicaciones()[0]).toEqual({
      metodo: 'POST',
      ruta: '/api/ejecuciones/e1/issue?tipo=tecnico&gravedad=media',
      header: '1',
    })
    const links = await screen.findAllByRole('link', { name: 'https://github.com/o/r/issues/7' })
    expect(links[0]).toHaveAttribute('href', 'https://github.com/o/r/issues/7')
  })

  it('un error 4xx del POST se muestra en un toast sin romper la pantalla', async () => {
    respuestaIssue = Response.json({ codigo: 'falta_header', detalle: 'falta el header X-Dogfood: 1' }, { status: 403 })
    const user = userEvent.setup()
    await montar()
    await user.click(screen.getByRole('button', { name: 'Crear issue' }))
    await user.click(within(await screen.findByRole('dialog')).getByRole('button', { name: 'Publicar' }))
    expect(await screen.findByText(/No se pudo crear el issue: falta el header X-Dogfood: 1/)).toBeInTheDocument()
    expect(screen.getByText('Paso 1 · pantalla 1')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Crear issue' })).toBeEnabled()
  })
})
