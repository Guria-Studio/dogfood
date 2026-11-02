import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import { ClipboardList, TriangleAlert } from 'lucide-react'
import { useState } from 'react'

import { cliente } from '@/api/cliente'
import type { components } from '@/api/schema'
import { Vacio } from '@/components/layout/Vacio'
import { Badge, type BadgeProps } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { duracion } from '@/features/corridas/comun'

export type Caso = components['schemas']['CasoVista']

const ESTADOS: Record<Caso['estado'], { texto: string; variante: BadgeProps['variant'] }> = {
  pendiente: { texto: 'Pendiente', variante: 'outline' },
  en_curso: { texto: 'En curso', variante: 'info' },
  exito: { texto: 'Éxito', variante: 'success' },
  fallo: { texto: 'Fallo', variante: 'danger' },
  rendido: { texto: 'Rendido', variante: 'warning' },
  no_concluyente: { texto: 'No concluyente', variante: 'neutral' },
}

export function BadgeEstado({ estado }: { estado: Caso['estado'] }) {
  const e = ESTADOS[estado]
  return (
    <Badge data-estado={estado} variant={e.variante}>
      {e.texto}
    </Badge>
  )
}

export function Filtro(props: { nombre: string; valor: string; opciones: [string, string][]; cambiar: (v: string) => void }) {
  return (
    <label className="flex flex-col gap-1 text-xs font-medium text-muted-foreground">
      {props.nombre}
      <select
        aria-label={props.nombre}
        value={props.valor}
        onChange={(e) => props.cambiar(e.target.value)}
        className="h-9 min-w-32 rounded-md border bg-background px-2 text-sm text-foreground"
      >
        <option value="">todos</option>
        {props.opciones.map(([v, t]) => (
          <option key={v} value={v}>
            {t}
          </option>
        ))}
      </select>
    </label>
  )
}

export function usePlan(corridaId: string) {
  return useQuery({
    queryKey: ['plan', corridaId],
    queryFn: async () => {
      const { data, error } = await cliente.GET('/api/corridas/{corrida_id}/plan', {
        params: { path: { corrida_id: corridaId } },
      })
      if (!data) throw new Error(String(error))
      return data
    },
    refetchInterval: (q) => (q.state.data?.some((c) => c.estado === 'en_curso' || c.estado === 'pendiente') ? 5000 : false),
  })
}

export const OPCIONES_ESTADO = Object.entries(ESTADOS).map(([v, e]) => [v, e.texto]) as [string, string][]
export const OPCIONES_PRIORIDAD: [string, string][] = [['alta', 'Alta'], ['media', 'Media']]

/** La tabla de casos (la vista Lista). */
export function ListaCasos({ casos }: { casos: Caso[] }) {
  const navigate = useNavigate()
  const abrir = (c: Caso) => c.ejecucion_id && navigate({ to: '/ejecuciones/$id', params: { id: c.ejecucion_id } })
  if (casos.length === 0) return <Vacio icono={ClipboardList} titulo="Ningún caso con esos filtros" />
  return (
    <Table>
      <TableHeader>
        <TableRow>
          {['Caso', 'Estado', 'Prioridad', 'Persona', 'Duración'].map((c) => (
            <TableHead key={c}>{c}</TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {casos.map((c) => (
          <TableRow
            key={c.id}
            data-caso={c.id}
            onClick={() => abrir(c)}
            className={c.ejecucion_id ? 'cursor-pointer' : undefined}
          >
            <TableCell>
              {c.ejecucion_id ? (
                <Link
                  to="/ejecuciones/$id"
                  params={{ id: c.ejecucion_id }}
                  onClick={(e) => e.stopPropagation()}
                  className="font-medium hover:underline"
                >
                  {c.titulo}
                </Link>
              ) : (
                <span className="font-medium">{c.titulo}</span>
              )}
              <div className="text-xs text-muted-foreground">{c.criterio_exito}</div>
            </TableCell>
            <TableCell>
              <BadgeEstado estado={c.estado} />
            </TableCell>
            <TableCell>
              <Badge variant={c.prioridad === 'alta' ? 'danger' : 'neutral'}>{c.prioridad}</Badge>
            </TableCell>
            <TableCell>{c.persona_nombre}</TableCell>
            <TableCell className="tabular-nums">{c.duracion_s == null ? '—' : duracion(c.duracion_s)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

/** Casos de prueba de la corrida: un caso por persona × escenario, con el estado de su ejecución. */
export function TablaCasos({ corridaId }: { corridaId: string }) {
  const [estado, setEstado] = useState('')
  const [prioridad, setPrioridad] = useState('')
  const plan = usePlan(corridaId)

  if (plan.isPending) return <Skeleton data-testid="cargando-casos" className="h-40 w-full" />
  if (plan.isError)
    return <Vacio icono={TriangleAlert} titulo="Sin plan de pruebas" texto="Esta corrida no guardó su plan (es anterior a los casos de prueba)." />

  const casos = plan.data.filter((c) => (!estado || c.estado === estado) && (!prioridad || c.prioridad === prioridad))
  return (
    <>
      <div className="mb-4 flex flex-wrap gap-3">
        <Filtro nombre="Estado" valor={estado} cambiar={setEstado} opciones={OPCIONES_ESTADO} />
        <Filtro nombre="Prioridad" valor={prioridad} cambiar={setPrioridad} opciones={OPCIONES_PRIORIDAD} />
      </div>
      <ListaCasos casos={casos} />
    </>
  )
}
