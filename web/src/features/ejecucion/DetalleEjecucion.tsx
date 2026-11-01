import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { Copy, TriangleAlert } from 'lucide-react'
import type { ReactNode } from 'react'

import { cliente } from '@/api/cliente'
import type { components } from '@/api/schema'
import { PageHeader } from '@/components/layout/PageHeader'
import { Vacio } from '@/components/layout/Vacio'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { toast } from '@/components/ui/sonner'
import { CrearIssue } from './CrearIssue'
import { lineaConsola, lineaRed } from './lineas'
import { Bloque, VisorPasos } from './VisorPasos'

type Detalle = components['schemas']['DetalleEjecucion']

const ETIQUETAS: Record<string, string> = {
  aprobado: 'aprobado',
  fallo: 'falló',
  no_concluyente: 'no concluyente',
}
const VARIANTE: Record<string, 'default' | 'destructive' | 'secondary'> = {
  aprobado: 'default',
  fallo: 'destructive',
}
const COMANDO_TRACE = 'uv run playwright show-trace trace.zip'

function duracion(s: number) {
  const m = Math.floor(s / 60)
  return m ? `${m} min ${Math.round(s % 60)} s` : `${s.toFixed(1)} s`
}

function Datos({ filas }: { filas: [string, ReactNode][] }) {
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
      {filas.map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-muted-foreground">{k}</dt>
          <dd className="min-w-0 break-words">{v}</dd>
        </div>
      ))}
    </dl>
  )
}

function Seccion({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <section className="space-y-3">
      <h2 className="text-lg font-semibold">{titulo}</h2>
      {children}
    </section>
  )
}

function copiar(texto: string) {
  navigator.clipboard?.writeText(texto).then(
    () => toast.success('Comando copiado'),
    () => toast.error('No se pudo copiar'),
  )
}

function Contenido({ d }: { d: Detalle }) {
  const { ejecucion: e, corrida: c, persona: p } = d
  const fricciones = Object.entries(d.fricciones)
  const general = [...d.consola.map(lineaConsola), ...d.red.map(lineaRed)]
  return (
    <div className="space-y-8">
      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Resultado</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Badge variant={VARIANTE[e.resultado] ?? 'secondary'}>
              {ETIQUETAS[e.resultado] ?? e.resultado}
            </Badge>
            {e.motivo_juez && <p className="text-sm text-muted-foreground">{e.motivo_juez}</p>}
            <Datos
              filas={[
                ['Recorrido', e.escenario_id],
                ['Driver', e.driver],
                ['Motor', `${e.motor}/${e.backend}`],
                ['Modelo', e.modelo],
                ['Duración', duracion(e.duracion_s)],
              ]}
            />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Persona</CardTitle>
          </CardHeader>
          <CardContent>
            <Datos
              filas={[
                ['Nombre', p.nombre],
                ['Idioma', p.idioma],
                ['Destreza', `${p.destreza}/5`],
                ['Intención', p.intencion],
              ]}
            />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Corrida</CardTitle>
          </CardHeader>
          <CardContent>
            <Datos
              filas={[
                [
                  'Corrida',
                  <Link to="/corridas/$id" params={{ id: c.id }} className="underline">
                    {c.id}
                  </Link>,
                ],
                ['Objetivo', c.objetivo],
                ['Versión', c.version],
                ['Ref', c.ref],
                ['Inicio', new Date(c.inicio).toLocaleString()],
                ['Estado', c.estado],
              ]}
            />
          </CardContent>
        </Card>
      </div>

      <Seccion titulo="Paso a paso">
        <VisorPasos pasos={d.pasos} />
      </Seccion>

      {d.video && (
        <Seccion titulo="Video">
          <video controls preload="metadata" src={d.video} className="w-full max-w-3xl rounded-md border" />
        </Seccion>
      )}

      {d.trace && (
        <Seccion titulo="Trace">
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <Button asChild variant="outline" size="sm">
              <a href={d.trace} download>
                Descargar trace.zip
              </a>
            </Button>
            <span className="text-muted-foreground">ábrelo con</span>
            <code className="rounded bg-muted px-2 py-1">{COMANDO_TRACE}</code>
            <Button variant="ghost" size="icon" aria-label="Copiar comando" onClick={() => copiar(COMANDO_TRACE)}>
              <Copy aria-hidden="true" />
            </Button>
          </div>
        </Seccion>
      )}

      {e.driver === 'web' && general.length > 0 && (
        <Seccion titulo="Consola y red de toda la ejecución">
          <Bloque lineas={general} vacio="" />
        </Seccion>
      )}

      {d.logcat && (
        <Seccion titulo="Logcat">
          <Bloque lineas={[d.logcat]} vacio="" />
        </Seccion>
      )}

      <Seccion titulo="Opinión de la persona">
        {fricciones.length === 0 && <p className="text-sm text-muted-foreground">Sin fricciones.</p>}
        {fricciones.map(([pantalla, items]) => (
          <div key={pantalla} className="space-y-2">
            <h3 className="font-medium">{pantalla}</h3>
            {items.map((f, i) => (
              <Card key={i}>
                <CardContent className="space-y-2 pt-6">
                  <p className="text-sm">
                    {f.texto} <Badge variant="outline">{f.severidad}</Badge>
                  </p>
                  {f.cita && (
                    <blockquote className="border-l-2 pl-3 text-sm text-muted-foreground italic">
                      {f.cita}
                    </blockquote>
                  )}
                  {f.captura && (
                    <img src={f.captura} alt="Captura de la fricción" className="max-w-sm rounded-md border" />
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        ))}
      </Seccion>
    </div>
  )
}

/** Pantalla de detalle de una ejecución (`/ejecuciones/$id`). */
export function DetalleEjecucion({ id }: { id: string }) {
  const q = useQuery({
    queryKey: ['ejecucion', id],
    queryFn: async () => {
      const { data, error } = await cliente.GET('/api/ejecuciones/{ejecucion_id}', {
        params: { path: { ejecucion_id: id } },
      })
      if (!data) throw new Error(JSON.stringify(error))
      return data
    },
  })
  const d = q.data
  // Mismo título que arma `panel/issue.py`.
  const titulo = d ? `${d.ejecucion.escenario_id} terminó en ${d.ejecucion.resultado}` : ''
  return (
    <>
      <PageHeader
        titulo={`Ejecución ${id}`}
        ayuda="ejecucion"
        descripcion={d ? `${d.persona.nombre} en ${d.ejecucion.escenario_id}` : undefined}
        acciones={d && <CrearIssue ejecucionId={id} titulo={titulo} />}
      />
      {q.isPending && <Skeleton className="h-64 w-full" />}
      {q.isError && (
        <Vacio error icono={TriangleAlert} titulo={`No se pudo cargar la ejecución ${id}`} texto="Puede que la ejecución no exista o que el panel no esté corriendo." accion={<Button asChild variant="outline"><Link to="/">Volver a corridas</Link></Button>} />
      )}
      {d && <Contenido d={d} />}
    </>
  )
}
