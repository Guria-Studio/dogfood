import { type ReactNode, useState } from 'react'

import { EncabezadoPagina } from '@/components/layout/EncabezadoPagina'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

import { type ProyectoAjustes, useGuardar, useProyecto } from './api'

export function Tarjeta(props: { titulo: string; texto?: string; children: ReactNode; peligro?: boolean }) {
  return (
    <Card className={props.peligro ? 'border-destructive/50' : undefined}>
      <CardHeader>
        <CardTitle className={props.peligro ? 'text-destructive' : undefined}>{props.titulo}</CardTitle>
        {props.texto && <CardDescription>{props.texto}</CardDescription>}
      </CardHeader>
      <CardContent className="space-y-4">{props.children}</CardContent>
    </Card>
  )
}

export const Ayuda = ({ children }: { children: ReactNode }) => <p className="text-sm text-muted-foreground">{children}</p>

export function Campo(props: { etiqueta: string; ayuda?: string; children: ReactNode }) {
  return (
    <label className="block space-y-1.5 text-sm font-medium">
      {props.etiqueta}
      {props.children}
      {props.ayuda && <span className="block text-sm font-normal text-muted-foreground">{props.ayuda}</span>}
    </label>
  )
}

export const clase =
  'flex w-full rounded-md border border-input bg-card px-3 py-2 text-sm shadow-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60'

export function Interruptor(props: { etiqueta: string; ayuda: string; valor: boolean; cambiar: (v: boolean) => void }) {
  return (
    <div className="flex items-start justify-between gap-4">
      <div>
        <p className="text-sm font-medium">{props.etiqueta}</p>
        <Ayuda>{props.ayuda}</Ayuda>
      </div>
      <input
        type="checkbox" role="switch" aria-label={props.etiqueta} checked={props.valor}
        onChange={(e) => props.cambiar(e.target.checked)} className="mt-1 size-5 accent-primary"
      />
    </div>
  )
}

/**
 * Página de ajustes: edita un borrador del proyecto y «Guardar cambios» solo se habilita si el
 * borrador difiere de lo guardado. `parte` elige qué campos de `ProyectoAjustes` se editan/envían.
 */
export function PaginaAjustes<K extends keyof ProyectoAjustes>(props: {
  slug: string
  titulo: string
  subtitulo: string
  campos: K[]
  children: (v: Pick<ProyectoAjustes, K>, cambiar: (c: Partial<Pick<ProyectoAjustes, K>>) => void, p: ProyectoAjustes) => ReactNode
  extra?: ReactNode
  /** Campos solo-escritura (p. ej. el webhook) que se envían pero no vuelven de la API. */
  secretos?: Record<string, unknown>
  limpiarSecretos?: () => void
}) {
  const { data: p, error } = useProyecto(props.slug)
  const guardar = useGuardar(props.slug)
  const [borrador, setBorrador] = useState<Partial<ProyectoAjustes>>({})
  const [msg, setMsg] = useState<string | null>(null)
  if (error) return <p role="alert">No se pudo cargar el proyecto: {error.message}</p>
  if (!p) return <p className="text-sm text-muted-foreground">Cargando…</p>
  const base = Object.fromEntries(props.campos.map((k) => [k, p[k]])) as Pick<ProyectoAjustes, K>
  const valor = { ...base, ...borrador } as Pick<ProyectoAjustes, K>
  const sucio = JSON.stringify(valor) !== JSON.stringify(base) || Object.values(props.secretos ?? {}).some(Boolean)
  const enviar = async () => {
    setMsg(null)
    try {
      const hay = Object.values(props.secretos ?? {}).some(Boolean)
      const v = valor as Record<string, unknown>
      await guardar(hay ? { ...v, notificaciones: { ...(v.notificaciones as object), ...props.secretos } } : v)
      setBorrador({})
      props.limpiarSecretos?.()
      setMsg('Cambios guardados')
    } catch (e) {
      setMsg(`No se pudo guardar: ${(e as Error).message}`)
    }
  }
  return (
    <>
      <EncabezadoPagina
        titulo={props.titulo}
        subtitulo={props.subtitulo}
        acciones={<Button disabled={!sucio} onClick={enviar}>Guardar cambios</Button>}
      />
      <div className="max-w-2xl space-y-4">
        {msg && <p role="status" className="text-sm">{msg}</p>}
        {props.children(valor, (c) => setBorrador((b) => ({ ...b, ...c })), p)}
        {props.extra}
      </div>
    </>
  )
}
