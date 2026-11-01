import { useQuery } from '@tanstack/react-query'

import { cliente } from '@/api/cliente'
import type { Filtros, Fila } from './TablaEjecuciones'

/** Ejecuciones con los filtros del servidor (los de la URL). La comparten la tabla y la portada. */
export function useEjecuciones(filtros: Filtros = {}) {
  return useQuery({
    queryKey: ['ejecuciones', filtros],
    queryFn: async () => {
      const { data, error } = await cliente.GET('/api/ejecuciones', { params: { query: filtros } })
      if (!data) throw new Error(String(error))
      return data
    },
  })
}

export interface PuntoCorrida {
  corrida: string
  exito: number
  costo: number
}

/** Agregados de la portada, calculados en el cliente desde `/api/ejecuciones`. */
export function calcularKpis(filas: Fila[]) {
  const total = filas.length
  const por = (r: string) => filas.filter((f) => f.resultado === r).length
  const grupos = new Map<string, Fila[]>()
  for (const f of filas) grupos.set(f.corrida_id, [...(grupos.get(f.corrida_id) ?? []), f])
  const inicio = (fs: Fila[]) => fs.reduce((m, f) => (f.fecha < m ? f.fecha : m), fs[0].fecha)
  const corridas = [...grupos.entries()].sort(([, a], [, b]) => inicio(a).localeCompare(inicio(b)))
  const ultimas: PuntoCorrida[] = corridas.slice(-10).map(([corrida, fs]) => ({
    corrida,
    exito: Math.round((fs.filter((f) => f.resultado === 'aprobado').length / fs.length) * 100),
    costo: Math.round(fs.reduce((s, f) => s + f.costo_usd, 0) * 100) / 100,
  }))
  return {
    total,
    corridas: corridas.length,
    exito: total ? Math.round((por('aprobado') / total) * 100) : 0,
    /** Gravedad del hallazgo según el resultado del juez: fallo (alta), rendido (media), no concluyente (baja). */
    hallazgos: { fallo: por('fallo'), rendido: por('rendido'), no_concluyente: por('no_concluyente') },
    ultimaCorrida: corridas.at(-1)?.[0],
    ultimas,
  }
}
