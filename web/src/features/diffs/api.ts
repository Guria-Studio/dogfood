import { useQuery } from '@tanstack/react-query'

/** Diffs de comportamiento (`panel/api_diffs.py`). Tipos a mano: reflejan `diff.py`. */
export interface ResumenDiff {
  id: string
  proyecto: string
  base: string
  nueva: string
  creado: string
  total: number
  con_cambios: number
}

export interface Cambio {
  tipo: 'red' | 'texto' | 'visual' | 'consola'
  gravedad: 'alta' | 'media' | 'baja'
  subtipo?: string
  metodo?: string
  ruta?: string
  antes?: string | number | null
  despues?: string | number | null
  texto?: string
  detalle?: string
}

export interface PasoDiff {
  step_id: string
  accion: string
  cambios: Cambio[]
  capturas?: { antes?: string; despues?: string }
}

export interface CasoDiff {
  tc: string
  caso_id: string
  titulo: string
  resultado: 'sin_cambios' | 'cambios' | 'no_alineado'
  motivo?: string
  pasos: PasoDiff[]
}

export interface Diff extends Omit<ResumenDiff, 'total' | 'con_cambios'> {
  casos: CasoDiff[]
}

async function pedir<T>(ruta: string): Promise<T> {
  const r = await globalThis.fetch(new URL(ruta, globalThis.location?.origin ?? 'http://localhost'))
  if (!r.ok) throw new Error(`error ${r.status}`)
  return r.json()
}

export const useDiffs = (proyecto: string) =>
  useQuery({
    queryKey: ['diffs', proyecto],
    queryFn: () => pedir<ResumenDiff[]>(`/api/proyectos/${proyecto}/diffs`),
  })

export const useDiff = (id: string) =>
  useQuery({
    queryKey: ['diff', id],
    queryFn: () => pedir<Diff>(`/api/diffs/${encodeURIComponent(id)}`),
  })

export async function lanzarDiff(proyecto: string, cuerpo: { base: string; nueva: string }): Promise<{ id: string }> {
  const r = await globalThis.fetch(
    new URL(`/api/proyectos/${proyecto}/diffs`, globalThis.location?.origin ?? 'http://localhost'),
    {
      method: 'POST',
      headers: { 'X-Dogfood': '1', 'Content-Type': 'application/json' },
      body: JSON.stringify(cuerpo),
    },
  )
  const d = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(typeof d.detail === 'string' ? d.detail : `error ${r.status}`)
  return d
}

export const urlCaptura = (id: string, ruta: string) =>
  `/api/diffs/${encodeURIComponent(id)}/${ruta.split('/').map(encodeURIComponent).join('/')}`
