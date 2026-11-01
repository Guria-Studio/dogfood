import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate, useSearch } from '@tanstack/react-router'
import { SearchX } from 'lucide-react'

import { cliente } from '@/api/cliente'
import { PageHeader } from '@/components/layout/PageHeader'
import { Vacio } from '@/components/layout/Vacio'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { TablaCasos } from '@/features/plan/TablaCasos'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { BadgeResultado, duracion, fecha, usd } from './comun'

function Tarjeta({ titulo, valor }: { titulo: string; valor: string | number }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium text-muted-foreground">{titulo}</CardTitle>
      </CardHeader>
      <CardContent className="text-2xl font-semibold">{valor}</CardContent>
    </Card>
  )
}

export function PantallaCorrida({ id }: { id: string }) {
  const { pestana } = useSearch({ strict: false }) as { pestana?: string }
  const navigate = useNavigate()
  const corrida = useQuery({
    queryKey: ['corrida', id],
    queryFn: async () => {
      const { data, error } = await cliente.GET('/api/corridas/{corrida_id}', {
        params: { path: { corrida_id: id } },
      })
      if (!data) throw new Error(String(error))
      return data
    },
  })
  const etiquetas = useQuery({
    queryKey: ['etiquetas'],
    queryFn: async () => (await cliente.GET('/api/etiquetas')).data ?? {},
  })

  const cabecera = <PageHeader
      titulo={`Corrida ${id}`}
      ayuda="corrida"
      acciones={<Button asChild variant="outline"><Link to="/corridas/$id/reporte" params={{ id }}>Reporte</Link></Button>}
    />
  if (corrida.isError)
    return (
      <>
        {cabecera}
        <Vacio error icono={SearchX} titulo="No se encontró la corrida" texto={`No hay datos de la corrida ${id}.`} accion={<Button asChild variant="outline"><Link to="/">Volver a corridas</Link></Button>} />
      </>
    )
  if (corrida.isPending)
    return (
      <>
        {cabecera}
        <Skeleton data-testid="cargando" className="h-40 w-full" />
      </>
    )

  const { resumen: r, comparacion } = corrida.data
  const total = r.por_resultado
  const aprobadas = total.aprobado ?? 0
  const exito = r.ejecuciones ? Math.round((aprobadas / r.ejecuciones) * 100) : 0
  const segundos = r.fin ? (Date.parse(r.fin) - Date.parse(r.inicio)) / 1000 : null
  const hallazgos = (total.fallo ?? 0) + (total.no_concluyente ?? 0)

  return (
    <>
      {cabecera}
      <Tabs
        value={pestana === 'casos' ? 'casos' : 'resumen'}
        onValueChange={(v) =>
          navigate({ to: '/corridas/$id', params: { id }, search: v === 'casos' ? { pestana: 'casos' } : {} })
        }
      >
        <TabsList className="mb-4">
          <TabsTrigger value="resumen">Resumen</TabsTrigger>
          <TabsTrigger value="casos">Casos de prueba</TabsTrigger>
        </TabsList>
        <TabsContent value="casos">
          <TablaCasos corridaId={id} />
        </TabsContent>
        <TabsContent value="resumen">
      <p className="mb-4 text-sm text-muted-foreground">
        {r.objetivo}@{r.ref} · versión {r.version} · {r.estado} · {fecha(r.inicio)} · {r.ejecuciones}{' '}
        ejecuciones
      </p>
      <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-5">
        <Tarjeta titulo="Personas" valor={r.n_personas} />
        <Tarjeta titulo="Éxito" valor={`${exito}%`} />
        <Tarjeta titulo="Hallazgos" valor={hallazgos} />
        <Tarjeta titulo="Costo" valor={usd(r.costo_usd)} />
        <Tarjeta titulo="Duración" valor={segundos === null ? '—' : duracion(segundos)} />
      </div>
      <p className="mb-6 flex flex-wrap items-center gap-3 text-sm">
        {Object.entries(total).map(([res, n]) => (
          <span key={res} className="flex items-center gap-1">
            <BadgeResultado resultado={res} etiqueta={etiquetas.data?.[res]} /> {n}
          </span>
        ))}
        · costo equivalente {usd(r.costo_equivalente_usd)}
      </p>
      <h2 className="mb-2 text-lg font-semibold">Comparación de motores</h2>
      <Table>
        <TableHeader>
          <TableRow>
            {['Motor', 'Backend', 'Modelo', 'Ejecuciones', 'Aprobadas', 'Falladas', 'No concluyentes',
              'Tasa de aprobación', 'Tokens/ejec.', 'Costo/ejec.', 'Costo equiv./ejec.'].map((c) => (
              <TableHead key={c}>{c}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {comparacion.map((m) => (
            <TableRow key={`${m.motor}/${m.backend}/${m.modelo}`}>
              <TableCell>{m.motor}</TableCell>
              <TableCell>{m.backend}</TableCell>
              <TableCell>{m.modelo}</TableCell>
              <TableCell>{m.ejecuciones}</TableCell>
              <TableCell>{m.aprobadas}</TableCell>
              <TableCell>{m.fallidas}</TableCell>
              <TableCell>{m.no_concluyentes}</TableCell>
              <TableCell>{Math.round(m.tasa_aprobacion * 100)}%</TableCell>
              <TableCell>{m.tokens}</TableCell>
              <TableCell>{usd(m.costo_usd)}</TableCell>
              <TableCell>{usd(m.costo_equivalente_usd)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
      <p className="mt-4 text-sm">
        <Link to="/" className="underline">
          Ver ejecuciones
        </Link>
      </p>
        </TabsContent>
      </Tabs>
    </>
  )
}
