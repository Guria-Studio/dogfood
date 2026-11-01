/** Acciones del panel (`panel/acciones.py`). Todas las que escriben mandan `X-Dogfood: 1`. */
export interface Estado {
  id: string
  estado: 'activa' | 'terminada' | 'cancelada'
  corrida_id: string | null
  terminados: number
  total: number
  en_curso: string[]
  log: string[]
}

export interface NuevaCorrida {
  objetivo: string
  ref: string
  personas: number
  escenarios: string[]
  sin_publicar: boolean
}

async function enviar(ruta: string, cuerpo?: unknown): Promise<{ id: string }> {
  const r = await globalThis.fetch(new URL(ruta, globalThis.location?.origin ?? 'http://localhost'), {
    method: 'POST',
    headers: { 'X-Dogfood': '1', ...(cuerpo ? { 'Content-Type': 'application/json' } : {}) },
    body: cuerpo ? JSON.stringify(cuerpo) : undefined,
  })
  const d = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(typeof d.detail === 'string' ? d.detail : `error ${r.status}`)
  return d
}

export const lanzarCorrida = (c: NuevaCorrida) =>
  enviar('/api/corridas', { ...c, escenarios: c.escenarios.length ? c.escenarios : null })
export const repetirCaso = (ejecucionId: string) =>
  enviar(`/api/ejecuciones/${encodeURIComponent(ejecucionId)}/replay`)
export const cancelar = (id: string) => enviar(`/api/corridas/${encodeURIComponent(id)}/cancelar`)

export async function estado(id: string): Promise<Estado> {
  const r = await globalThis.fetch(new URL(`/api/corridas/${encodeURIComponent(id)}/estado`, globalThis.location?.origin ?? 'http://localhost'))
  if (!r.ok) throw new Error(`error ${r.status}`)
  return r.json()
}
