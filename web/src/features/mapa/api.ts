import { useQuery } from '@tanstack/react-query'

/** Mapa de la última exploración (`panel/api_escenarios.py`). */
export interface Pantalla { path: string; url: string; titulo: string; acciones: string[]; captura: string | null }
export interface CasoUso { id: string; nombre: string; pantallas: string[]; estado: 'visto' | 'solo_prd' }
export interface Funcionalidad { nombre: string; casos: CasoUso[] }
export interface Mapa { id: string; creado: string; pantallas: Pantalla[]; funcionalidades: Funcionalidad[] }

const url = (r: string) => new URL(r, globalThis.location?.origin ?? 'http://localhost')
const ruta = (slug: string, sufijo: string) => `/api/proyectos/${encodeURIComponent(slug)}${sufijo}`

export const urlCaptura = (slug: string, path: string) => ruta(slug, `/mapa/captura?path=${encodeURIComponent(path)}`)

/** `null` si el proyecto todavía no se exploró (404). */
export const useMapa = (slug: string) =>
  useQuery({
    queryKey: ['mapa', slug],
    queryFn: async (): Promise<Mapa | null> => {
      const r = await globalThis.fetch(url(ruta(slug, '/mapa')))
      if (r.status === 404) return null
      if (!r.ok) throw new Error(`error ${r.status}`)
      return r.json()
    },
  })

/** Equivale a `dogfood explorar --proyecto <slug>`; devuelve el id del lanzamiento. */
export async function explorar(slug: string): Promise<{ id: string }> {
  const r = await globalThis.fetch(url(ruta(slug, '/exploraciones')), { method: 'POST', headers: { 'X-Dogfood': '1' } })
  const d = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(typeof d.detail === 'string' ? d.detail : `error ${r.status}`)
  return d
}
