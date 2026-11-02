import { useQuery } from '@tanstack/react-query'

/** Escenarios propuestos de un proyecto web (`panel/api_escenarios.py`). */
export interface EscenarioProyecto {
  id: string
  titulo: string
  objetivo: string
  criterio_exito: string
  superficies: string[]
  prioridad: 'alta' | 'media'
  estado: 'borrador' | 'aceptado' | 'descartado'
}

const url = (r: string) => new URL(r, globalThis.location?.origin ?? 'http://localhost')
const ruta = (slug: string, sufijo = '') => `/api/proyectos/${encodeURIComponent(slug)}/escenarios${sufijo}`

export const useEscenarios = (slug: string, estado?: EscenarioProyecto['estado']) =>
  useQuery({
    queryKey: ['escenarios', slug, estado ?? ''],
    queryFn: async (): Promise<EscenarioProyecto[]> => {
      const r = await globalThis.fetch(url(ruta(slug) + (estado ? `?estado=${estado}` : '')))
      if (!r.ok) throw new Error(`error ${r.status}`)
      return r.json()
    },
  })

/** PATCH de un escenario: `estado`, `prioridad`, `titulo`, `objetivo`… */
export async function editarEscenario(slug: string, id: string, cambios: Partial<EscenarioProyecto>) {
  const r = await globalThis.fetch(url(ruta(slug, `/${encodeURIComponent(id)}`)), {
    method: 'PATCH',
    headers: { 'X-Dogfood': '1', 'Content-Type': 'application/json' },
    body: JSON.stringify(cambios),
  })
  const d = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(typeof d.detail === 'string' ? d.detail : `error ${r.status}`)
  return d as EscenarioProyecto
}
