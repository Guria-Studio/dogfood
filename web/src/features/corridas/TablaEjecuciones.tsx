import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'

import { cliente } from '@/api/cliente'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { BadgeResultado, duracion, fecha, usd } from './comun'

export const FILTROS = ['recorrido', 'resultado', 'version', 'persona', 'driver', 'motor'] as const
export type Filtros = Partial<Record<(typeof FILTROS)[number], string>>

/** Para `validateSearch` de la ruta: solo claves conocidas con texto no vacío. */
export function validarFiltros(s: Record<string, unknown>): Filtros {
  const f: Filtros = {}
  for (const k of FILTROS) if (typeof s[k] === 'string' && s[k]) f[k] = s[k] as string
  return f
}

const COLUMNAS = [
  'Corrida', 'Fecha', 'Versión', 'Persona', 'Escenario', 'Driver', 'Motor', 'Backend', 'Modelo',
  'Resultado', 'Duración', 'Pasos', 'Tokens', 'Capturas', 'Costo', 'Costo equiv.',
]

export function TablaEjecuciones({ filtros }: { filtros: Filtros }) {
  const navigate = useNavigate()
  const ejecuciones = useQuery({
    queryKey: ['ejecuciones', filtros],
    queryFn: async () => {
      const { data, error } = await cliente.GET('/api/ejecuciones', { params: { query: filtros } })
      if (!data) throw new Error(String(error))
      return data
    },
  })
  const etiquetas = useQuery({
    queryKey: ['etiquetas'],
    queryFn: async () => (await cliente.GET('/api/etiquetas')).data ?? {},
  })

  if (ejecuciones.isError) return <p role="alert">No se pudieron cargar las ejecuciones.</p>
  if (ejecuciones.isPending)
    return (
      <div data-testid="cargando" className="space-y-2">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-9 w-full" />
        ))}
      </div>
    )
  if (ejecuciones.data.length === 0)
    return (
      <p className="text-muted-foreground">
        Sin ejecuciones.{' '}
        <Link to="/ayuda/$slug" params={{ slug: 'primera-corrida' }} className="underline">
          Cómo correr dogfood
        </Link>
      </p>
    )

  return (
    <Table>
      <TableHeader>
        <TableRow>
          {COLUMNAS.map((c) => (
            <TableHead key={c}>{c}</TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {ejecuciones.data.map((f) => (
          <TableRow
            key={f.id}
            className="cursor-pointer"
            onClick={() => navigate({ to: '/ejecuciones/$id', params: { id: f.id } })}
          >
            <TableCell>
              <Link
                to="/corridas/$id"
                params={{ id: f.corrida_id }}
                onClick={(e) => e.stopPropagation()}
                className="underline"
              >
                {f.corrida_id}
              </Link>
            </TableCell>
            <TableCell>{fecha(f.fecha)}</TableCell>
            <TableCell>{f.version}</TableCell>
            <TableCell>
              {f.persona_nombre ?? f.persona_id} ({f.persona_idioma ?? '?'})
            </TableCell>
            <TableCell>{f.escenario_id}</TableCell>
            <TableCell>{f.driver}</TableCell>
            <TableCell>{f.motor}</TableCell>
            <TableCell>{f.backend}</TableCell>
            <TableCell>{f.modelo}</TableCell>
            <TableCell>
              <BadgeResultado resultado={f.resultado} etiqueta={etiquetas.data?.[f.resultado]} />
            </TableCell>
            <TableCell>{duracion(f.duracion_s)}</TableCell>
            <TableCell>{f.pasos}</TableCell>
            <TableCell>{f.tokens}</TableCell>
            <TableCell>{f.capturas}</TableCell>
            <TableCell>{usd(f.costo_usd)}</TableCell>
            <TableCell>{usd(f.costo_equivalente_usd)}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
