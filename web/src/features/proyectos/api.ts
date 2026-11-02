import { useQuery } from '@tanstack/react-query'

/** API de proyectos (`panel/api_proyectos.py`). Las que escriben mandan `X-Dogfood: 1`. */
export interface ProyectoLista {
  slug: string
  nombre: string
  tipo: 'web' | 'android' | 'ios' | 'flutter_web'
  creado: string | null
  origen?: 'Panel' | 'CLI' | 'Slack'
  notificaciones: { slack: boolean; issues_github: boolean; repo: string }
  ultimos: { corrida_id: string | null; pasaron: number; fallaron: number; ultima_actividad: string | null }
}

const base = () => globalThis.location?.origin ?? 'http://localhost'

export function useProyectos() {
  return useQuery({
    queryKey: ['proyectos'],
    queryFn: async (): Promise<ProyectoLista[]> => {
      const r = await globalThis.fetch(new URL('/api/proyectos', base()))
      if (!r.ok) throw new Error(`error ${r.status}`)
      return r.json()
    },
  })
}

async function enviar(ruta: string, cuerpo?: unknown) {
  const r = await globalThis.fetch(new URL(ruta, base()), {
    method: 'POST',
    headers: { 'X-Dogfood': '1', ...(cuerpo ? { 'Content-Type': 'application/json' } : {}) },
    body: cuerpo ? JSON.stringify(cuerpo) : undefined,
  })
  const d = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(typeof d.detail === 'string' ? d.detail : `error ${r.status}`)
  return d
}

export const crearProyecto = (datos: Record<string, unknown>) => enviar('/api/proyectos', datos)
/** Equivale a `dogfood plan --target <slug>`. */
export const generarPlan = (slug: string) => enviar(`/api/proyectos/${encodeURIComponent(slug)}/plan`)

export const ETIQUETA_TIPO = { web: 'Web', flutter_web: 'Web', android: 'Android', ios: 'iOS' } as const
