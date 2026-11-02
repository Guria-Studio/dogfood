import { useQuery, useQueryClient } from '@tanstack/react-query'

/** API de ajustes del proyecto (`panel/api_proyectos.py`). Las que escriben mandan `X-Dogfood: 1`. */
export interface Entorno { nombre: string; url: string; predeterminado: boolean }
export interface ProyectoAjustes {
  slug: string
  nombre: string
  tipo: 'web' | 'android' | 'ios' | 'flutter_web'
  instrucciones: string
  acceso: { usuario: string; secreto_ref: string }
  entornos: Entorno[]
  comportamiento: { login_una_vez: boolean; viewport: 'escritorio' | 'movil'; concurrencia: number | null }
  notificaciones: { slack: boolean; issues_github: boolean; repo: string; etiqueta: string; comentar_pr: boolean }
}
export interface Evento { id: number; tipo: string; detalle: string; autor: string; fecha: string }
export interface Fuente { tipo: 'prd' | 'docs' | 'repo' | 'exploracion'; nombre: string; ruta: string }

const url = (r: string) => new URL(r, globalThis.location?.origin ?? 'http://localhost')
const ruta = (slug: string, sufijo = '') => `/api/proyectos/${encodeURIComponent(slug)}${sufijo}`

async function pedir(r: string, init?: RequestInit) {
  const res = await globalThis.fetch(url(r), init)
  const d = await res.json().catch(() => ({}))
  if (!res.ok) throw new Error(typeof d.detail === 'string' ? d.detail : `error ${res.status}`)
  return d
}
const escribir = (r: string, metodo: string, cuerpo?: unknown) =>
  pedir(r, {
    method: metodo,
    headers: { 'X-Dogfood': '1', ...(cuerpo ? { 'Content-Type': 'application/json' } : {}) },
    body: cuerpo ? JSON.stringify(cuerpo) : undefined,
  })

export const useProyecto = (slug: string) =>
  useQuery({ queryKey: ['proyecto', slug], queryFn: (): Promise<ProyectoAjustes> => pedir(ruta(slug)) })
export const useActividad = (slug: string) =>
  useQuery({ queryKey: ['actividad', slug], queryFn: (): Promise<Evento[]> => pedir(ruta(slug, '/actividad')) })
export const useFuentes = (slug: string) =>
  useQuery({ queryKey: ['fuentes', slug], queryFn: (): Promise<Fuente[]> => pedir(ruta(slug, '/fuentes')) })

export function useGuardar(slug: string) {
  const qc = useQueryClient()
  return async (cambios: Record<string, unknown>) => {
    await escribir(ruta(slug), 'PATCH', cambios)
    await Promise.all(['proyecto', 'proyectos', 'actividad'].map((k) => qc.invalidateQueries({ queryKey: [k] })))
  }
}
export const borrarProyecto = (slug: string) => escribir(ruta(slug), 'DELETE', { confirmar: slug })
export const probarSlack = (slug: string) => escribir(ruta(slug, '/slack/probar'), 'POST')
