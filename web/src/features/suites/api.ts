import { useQuery, useQueryClient } from '@tanstack/react-query'

/** API de suites y programaciones (`panel/api_suites.py`). Las que escriben mandan `X-Dogfood: 1`. */
export type EstadoSuite = 'paso' | 'advertencia' | 'fallo' | 'bloqueado' | 'corriendo'
export interface CasoRef { proyecto: string; caso: string }
export interface Suite {
  id: number
  nombre: string
  casos: CasoRef[]
  n_casos: number
  ultima_ejecucion: string | null
  estado: EstadoSuite | null
}
export interface Programacion {
  id: number
  suite_id: number
  suite: string
  frecuencia: 'hora' | 'dia' | 'semana' | 'cron'
  hora: string
  dia: string
  cron: string
  slack: boolean
  calendario: string
}
export interface CasoElegible { proyecto: string; caso: string; nombre: string }

async function pedir(r: string, init?: RequestInit) {
  const res = await globalThis.fetch(new URL(r, globalThis.location?.origin ?? 'http://localhost'), init)
  const d = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(typeof d.detail === 'string' ? d.detail : `error ${res.status}`)
  return d
}
export const escribir = (r: string, metodo: string, cuerpo?: unknown) =>
  pedir(r, {
    method: metodo,
    headers: { 'X-Dogfood': '1', ...(cuerpo ? { 'Content-Type': 'application/json' } : {}) },
    body: cuerpo ? JSON.stringify(cuerpo) : undefined,
  })

export const useSuites = () => useQuery({ queryKey: ['suites'], queryFn: (): Promise<Suite[]> => pedir('/api/suites') })
export const useProgramaciones = () =>
  useQuery({ queryKey: ['programaciones'], queryFn: (): Promise<Programacion[]> => pedir('/api/programaciones') })

/** Los casos de todos los proyectos, para el selector. */
export const useCasosElegibles = () =>
  useQuery({
    queryKey: ['casos-elegibles'],
    queryFn: async (): Promise<CasoElegible[]> => {
      const ps: { slug: string }[] = await pedir('/api/proyectos')
      const listas = await Promise.all(
        ps.map(async (p) => {
          const l = await pedir(`/api/proyectos/${encodeURIComponent(p.slug)}/casos`)
          return (l.grupos ?? []).flatMap((g: { casos: { id: string; nombre: string }[] }) =>
            g.casos.map((c) => ({ proyecto: p.slug, caso: c.id, nombre: c.nombre })),
          )
        }),
      )
      return listas.flat()
    },
  })

export function useRefrescar() {
  const qc = useQueryClient()
  return () => Promise.all(['suites', 'programaciones'].map((k) => qc.invalidateQueries({ queryKey: [k] })))
}
