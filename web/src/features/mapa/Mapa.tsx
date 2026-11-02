import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useParams } from '@tanstack/react-router'
import { Compass } from 'lucide-react'
import { useState } from 'react'

import { estado } from '@/features/acciones/api'
import { EncabezadoPagina } from '@/components/layout/EncabezadoPagina'
import { Vacio } from '@/components/layout/Vacio'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { explorar, type Mapa as MapaDatos, urlCaptura, useMapa } from './api'

function Miniatura({ slug, path, mapa }: { slug: string; path: string; mapa: MapaDatos }) {
  const p = mapa.pantallas.find((x) => x.path === path)
  return (
    <figure data-pantalla={path} className="w-20 text-center text-[10px] text-muted-foreground">
      {p?.captura ? (
        <img src={urlCaptura(slug, path)} alt={`Pantalla ${p.titulo || path}`} loading="lazy" className="h-14 w-20 rounded border object-cover object-top" />
      ) : (
        <div className="h-14 w-20 rounded border bg-muted" />
      )}
      <figcaption className="truncate">{path}</figcaption>
    </figure>
  )
}

/** Progreso en vivo de una exploración lanzada (sondea cada 2 s mientras está activa). */
function ProgresoExploracion({ id, slug }: { id: string; slug: string }) {
  const qc = useQueryClient()
  const q = useQuery({
    queryKey: ['lanzamiento', id],
    queryFn: async () => {
      const e = await estado(id)
      if (e.estado !== 'activa') {
        qc.invalidateQueries({ queryKey: ['mapa', slug] })
        qc.invalidateQueries({ queryKey: ['escenarios', slug] })
      }
      return e
    },
    refetchInterval: (c) => (!c.state.data || c.state.data.estado === 'activa' ? 2000 : false),
  })
  const e = q.data
  return (
    <div role="status" className="mb-4 rounded-lg border bg-card p-3 text-sm">
      {!e || e.estado === 'activa' ? 'Explorando la app…' : e.estado === 'terminada' ? 'Exploración terminada.' : 'Exploración cancelada.'}
      {e && e.log.length > 0 && <p className="mt-1 truncate font-mono text-xs text-muted-foreground">{e.log[e.log.length - 1]}</p>}
    </div>
  )
}

/** Mapa de funcionalidades de la app: lo que dogfood vio y lo que el PRD promete y no apareció. */
export function Mapa({ slug: slugProp }: { slug?: string }) {
  const params = useParams({ strict: false }) as { proyecto?: string }
  const slug = slugProp ?? params.proyecto ?? ''
  const mapa = useMapa(slug)
  const [lanzada, setLanzada] = useState<string | null>(null)
  const lanzar = useMutation({ mutationFn: () => explorar(slug), onSuccess: (d) => setLanzada(d.id) })
  const boton = (
    <Button onClick={() => lanzar.mutate()} disabled={lanzar.isPending}>
      {mapa.data ? 'Explorar de nuevo' : 'Explorar la app'}
    </Button>
  )
  return (
    <>
      <EncabezadoPagina titulo="Mapa" subtitulo="Las funcionalidades de la app, sus casos de uso y las pantallas donde ocurren." acciones={boton} />
      {lanzar.error && <p role="alert" className="mb-3 text-sm text-danger">{lanzar.error.message}</p>}
      {lanzada && <ProgresoExploracion id={lanzada} slug={slug} />}
      {mapa.data === null && !lanzada && (
        <Vacio icono={Compass} titulo="Todavía no se exploró" texto="Explora la app y dogfood arma el mapa y propone escenarios para revisar." />
      )}
      <div className="grid gap-4 md:grid-cols-2">
        {mapa.data?.funcionalidades.map((f) => (
          <Card key={f.nombre} data-funcionalidad={f.nombre}>
            <CardHeader><CardTitle>{f.nombre}</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              {f.casos.map((c) => (
                <div key={c.id} data-caso={c.id} data-estado={c.estado} className="space-y-1.5">
                  <p className="flex flex-wrap items-center gap-2 text-sm font-medium">
                    {c.nombre}
                    {c.estado === 'solo_prd' ? (
                      <span className="rounded bg-amber-100 px-1.5 py-0.5 text-xs font-normal text-amber-900 dark:bg-amber-950 dark:text-amber-200">solo_prd · posible brecha</span>
                    ) : (
                      <span className="rounded bg-muted px-1.5 py-0.5 text-xs font-normal text-muted-foreground">visto</span>
                    )}
                  </p>
                  {c.pantallas.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {c.pantallas.map((p) => <Miniatura key={p} slug={slug} path={p} mapa={mapa.data!} />)}
                    </div>
                  )}
                </div>
              ))}
            </CardContent>
          </Card>
        ))}
      </div>
    </>
  )
}
