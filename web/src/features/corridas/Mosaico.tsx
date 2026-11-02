import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { Radio } from 'lucide-react'
import { useMemo, useState } from 'react'

import { cliente } from '@/api/cliente'
import { RepetirCaso } from '@/features/acciones/RepetirCaso'
import { Vacio } from '@/components/layout/Vacio'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import {
  type Caso,
  Filtro,
  ListaCasos,
  OPCIONES_ESTADO,
  OPCIONES_PRIORIDAD,
  usePlan,
} from '@/features/plan/TablaCasos'
import { type Ejecucion, useVista } from '@/features/vivo/useVista'

type Estado = Caso['estado']

/** Los cuatro grupos del mosaico; ponytail: «pendiente» (aún no corre) va con Corriendo, «rendido» con Fallaron. */
export const GRUPOS: { clave: string; titulo: string; estados: Estado[] }[] = [
  { clave: 'corriendo', titulo: 'Corriendo', estados: ['en_curso', 'pendiente'] },
  { clave: 'pasaron', titulo: 'Pasaron', estados: ['exito'] },
  { clave: 'fallaron', titulo: 'Fallaron', estados: ['fallo', 'rendido'] },
  { clave: 'bloqueados', titulo: 'Bloqueados', estados: ['no_concluyente'] },
]

const POR_RESULTADO: Record<string, Estado> = { aprobado: 'exito', fallo: 'fallo', rendido: 'rendido' }

/** Aplica lo que llegó por el websocket: el último frame y el resultado final de la ejecución. */
function conVivo(c: Caso, vivo: Ejecucion[]): { caso: Caso; frame: string | null } {
  const e = vivo.find((v) => v.id === c.ejecucion_id || c.ejecuciones.includes(v.id))
  if (!e) return { caso: c, frame: null }
  const estado = e.resultado === null ? (c.estado === 'pendiente' ? 'en_curso' : c.estado) : (POR_RESULTADO[e.resultado] ?? 'no_concluyente')
  return { caso: { ...c, estado, ejecucion_id: c.ejecucion_id ?? e.id }, frame: e.frame }
}

function Tarjeta({ caso, frame }: { caso: Caso; frame: string | null }) {
  const id = caso.ejecucion_id
  const detalle = useQuery({
    queryKey: ['ejecucion', id],
    enabled: !!id,
    queryFn: async () => {
      const { data } = await cliente.GET('/api/ejecuciones/{ejecucion_id}', { params: { path: { ejecucion_id: id! } } })
      return data ?? null
    },
  })
  const d = detalle.data
  const captura = [...(d?.pasos ?? [])].reverse().find((p) => p.captura)?.captura
  const enVivo = caso.estado === 'en_curso'
  const falla = caso.estado === 'fallo' || caso.estado === 'rendido'
  const diagnostico = falla ? (d?.ejecucion.motivo_juez ?? '').split('\n')[0] : ''
  const telefono = !!d && d.ejecucion.driver !== 'web'
  const imagen = frame ?? captura

  return (
    <li data-testid="tarjeta" data-caso={caso.id} data-estado={caso.estado} className="flex flex-col gap-2 rounded-lg border bg-card p-3">
      <div className={telefono ? 'mx-auto w-28 rounded-[1.25rem] border-4 border-foreground/80 p-0.5' : 'w-full'} data-telefono={telefono || undefined}>
        {d?.video && !enVivo ? (
          <video src={d.video} controls muted className="aspect-video w-full rounded bg-muted object-cover" />
        ) : imagen ? (
          <img src={imagen} alt={`Pantalla de ${caso.persona_nombre}`} className="w-full rounded bg-muted object-cover" />
        ) : (
          <Skeleton className="aspect-video w-full" />
        )}
      </div>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          {id ? (
            <Link to="/ejecuciones/$id" params={{ id }} className="font-medium hover:underline">
              {caso.titulo}
            </Link>
          ) : (
            <span className="font-medium">{caso.titulo}</span>
          )}
          <div className="text-xs text-muted-foreground">{caso.persona_nombre}</div>
        </div>
        {enVivo && (
          <Badge variant="danger" className="shrink-0 gap-1">
            <Radio aria-hidden="true" className="size-3" /> EN VIVO
          </Badge>
        )}
      </div>
      {diagnostico && <p className="line-clamp-1 text-xs text-destructive">{diagnostico}</p>}
      {falla && id && <RepetirCaso ejecucionId={id} />}
    </li>
  )
}

/** Vista «Acciones del agente» (mosaico) o «Lista» sobre los mismos casos, con filtros y tarjetas en vivo. */
export function Mosaico({ corridaId, vista }: { corridaId: string; vista: 'acciones' | 'lista' }) {
  const plan = usePlan(corridaId)
  const { ejecuciones } = useVista()
  const [q, setQ] = useState('')
  const [estado, setEstado] = useState('')
  const [prioridad, setPrioridad] = useState('')

  const filas = useMemo(() => (plan.data ?? []).map((c) => conVivo(c, ejecuciones)), [plan.data, ejecuciones])
  if (plan.isPending) return <Skeleton data-testid="cargando-casos" className="h-40 w-full" />
  if (plan.isError) return <Vacio titulo="Sin plan de pruebas" texto="Esta corrida no guardó su plan." />

  const n = q.trim().toLowerCase()
  const visibles = filas.filter(
    ({ caso: c }) =>
      (!estado || c.estado === estado) &&
      (!prioridad || c.prioridad === prioridad) &&
      (!n || `${c.titulo} ${c.persona_nombre}`.toLowerCase().includes(n)),
  )
  const pasaron = filas.filter((f) => f.caso.estado === 'exito').length
  const tasa = filas.length ? Math.round((pasaron / filas.length) * 100) : 0

  return (
    <>
      <p className="mb-3 text-sm">
        Tasa de éxito: <strong>{tasa}%</strong> ({pasaron} de {filas.length})
      </p>
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <Input aria-label="Buscar caso" placeholder="Buscar caso o persona…" value={q} onChange={(e) => setQ(e.target.value)} className="h-9 w-56" />
        <Filtro nombre="Estado" valor={estado} cambiar={setEstado} opciones={OPCIONES_ESTADO} />
        <Filtro nombre="Prioridad" valor={prioridad} cambiar={setPrioridad} opciones={OPCIONES_PRIORIDAD} />
      </div>
      {vista === 'lista' ? (
        <ListaCasos casos={visibles.map((f) => f.caso)} />
      ) : (
        GRUPOS.map((g) => {
          const items = visibles.filter((f) => g.estados.includes(f.caso.estado))
          return (
            <section key={g.clave} data-grupo={g.clave} aria-labelledby={`g-${g.clave}`} className="mb-6">
              <h3 id={`g-${g.clave}`} className="mb-2 text-sm font-semibold">
                {g.titulo} <span data-conteo className="text-muted-foreground">{items.length}</span>
              </h3>
              {items.length > 0 && (
                <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                  {items.map((f) => (
                    <Tarjeta key={f.caso.id} caso={f.caso} frame={f.frame} />
                  ))}
                </ul>
              )}
            </section>
          )
        })
      )}
    </>
  )
}
