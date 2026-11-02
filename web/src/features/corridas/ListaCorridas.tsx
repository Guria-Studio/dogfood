import { useQuery } from '@tanstack/react-query'
import { Link, useParams } from '@tanstack/react-router'
import { useState } from 'react'

import { cliente } from '@/api/cliente'
import { EncabezadoPagina } from '@/components/layout/EncabezadoPagina'
import { Vacio } from '@/components/layout/Vacio'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { NuevaCorrida } from '@/features/acciones/NuevaCorrida'
import { duracion, fecha, usd } from './comun'
import { Kpis } from './Kpis'
import { PantallaCorridas } from './PantallaCorridas'

/** Corridas del proyecto: estado, entorno, casos que pasaron, costo, duración y fecha. */
export function ListaCorridas() {
  const { proyecto } = useParams({ strict: false }) as { proyecto: string }
  const [q, setQ] = useState('')
  const corridas = useQuery({
    queryKey: ['corridas', proyecto, q],
    queryFn: async () => {
      const { data, error } = await cliente.GET('/api/proyectos/{slug}/corridas', {
        params: { path: { slug: proyecto }, query: { q } },
      })
      if (!data) throw new Error(JSON.stringify(error))
      return data
    },
    placeholderData: (previo) => previo,
  })

  return (
    <>
      <EncabezadoPagina titulo="Corridas" ayuda="corridas" acciones={<NuevaCorrida />} subtitulo="Cómo les fue a las personas en cada corrida." />
      <Kpis />
      <h2 className="mb-3 text-lg font-semibold tracking-tight">Historial de corridas</h2>
      <Input aria-label="Buscar corrida" placeholder="Buscar corrida…" value={q} onChange={(e) => setQ(e.target.value)} className="mb-4 h-9 w-64" />
      {corridas.isPending ? (
        <Skeleton className="h-40 w-full" />
      ) : corridas.data?.length ? (
        <Table>
          <TableHeader>
            <TableRow>
              {['Corrida', 'Estado', 'Entorno', 'Pasaron', 'Costo', 'Duración', 'Fecha'].map((c) => (
                <TableHead key={c}>{c}</TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {corridas.data.map((c) => (
              <TableRow key={c.id} data-corrida={c.id}>
                <TableCell>
                  <Link to="/proyectos/$proyecto/corridas/$id" params={{ proyecto, id: c.id }} className="font-medium hover:underline">
                    {c.id}
                  </Link>
                </TableCell>
                <TableCell>{c.estado}</TableCell>
                <TableCell>{c.entorno}</TableCell>
                <TableCell className="tabular-nums">
                  {c.pasaron} de {c.total}
                </TableCell>
                <TableCell className="tabular-nums">{usd(c.costo_usd)}</TableCell>
                <TableCell className="tabular-nums">{c.duracion_s == null ? '—' : duracion(c.duracion_s)}</TableCell>
                <TableCell>{fecha(c.inicio)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : (
        <Vacio titulo="Sin corridas" texto="Lanza la primera con «Nueva corrida»." />
      )}
      <div className="mt-8">
        <PantallaCorridas />
      </div>
    </>
  )
}
