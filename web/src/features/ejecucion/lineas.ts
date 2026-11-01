import type { components } from '@/api/schema'

export const lineaConsola = (c: components['schemas']['EventoConsola']) => `[${c.nivel}] ${c.texto}`

export const lineaRed = (r: components['schemas']['EventoRed']) =>
  `${r.metodo} ${r.url} → ${r.estado} (${Math.round(r.ms)} ms)`
