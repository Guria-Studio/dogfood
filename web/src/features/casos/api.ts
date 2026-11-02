import { useQuery } from '@tanstack/react-query'

import { cliente } from '@/api/cliente'
import type { components } from '@/api/schema'

export type ListaCasos = components['schemas']['ListaCasos']
export type CasoFila = components['schemas']['CasoFila']
export type DetalleCaso = components['schemas']['DetalleCaso']

export interface FiltrosCasos {
  estado?: string
  q?: string
  prioridad?: string
}

export function useCasos(proyecto: string, f: FiltrosCasos) {
  return useQuery({
    queryKey: ['casos', proyecto, f.estado ?? '', f.q ?? '', f.prioridad ?? ''],
    queryFn: async () => {
      const { data, error } = await cliente.GET('/api/proyectos/{slug}/casos', {
        params: { path: { slug: proyecto }, query: { estado: f.estado ?? '', q: f.q ?? '', prioridad: f.prioridad ?? '' } },
      })
      if (!data) throw new Error(JSON.stringify(error))
      return data
    },
    placeholderData: (previo) => previo, // sin parpadeo al cambiar de pestaña o al buscar
  })
}

export function useCaso(proyecto: string, tc: string) {
  return useQuery({
    queryKey: ['caso', proyecto, tc],
    queryFn: async () => {
      const { data, error } = await cliente.GET('/api/proyectos/{slug}/casos/{tc}', {
        params: { path: { slug: proyecto, tc } },
      })
      if (!data) throw new Error(JSON.stringify(error))
      return data
    },
  })
}

const RTF = new Intl.RelativeTimeFormat('es', { numeric: 'auto' })
const UNIDADES: [Intl.RelativeTimeFormatUnit, number][] = [
  ['year', 31536000],
  ['month', 2592000],
  ['day', 86400],
  ['hour', 3600],
  ['minute', 60],
]

/** «hace 10 meses», «hace 3 horas»… */
export function hace(fecha: string, ahora = Date.now()): string {
  const s = (new Date(fecha).getTime() - ahora) / 1000
  for (const [u, n] of UNIDADES) if (Math.abs(s) >= n) return RTF.format(Math.round(s / n), u)
  return 'recién'
}
