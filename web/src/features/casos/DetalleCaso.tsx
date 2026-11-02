import { Link } from '@tanstack/react-router'
import { ClipboardCopy, Link2, Maximize2, Sparkles, TriangleAlert } from 'lucide-react'
import type { ReactNode } from 'react'

import { Avatar, Prioridad } from '@/components/comun/Datos'
import { BadgeEstado } from '@/components/comun/Estado'
import { Vacio } from '@/components/layout/Vacio'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { toast } from '@/components/ui/sonner'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'
import { type DetalleCaso as Detalle, hace, useCaso } from './api'

const FALLIDOS = new Set(['fallo', 'bloqueado', 'no_concluyente'])

function copiar(texto: string, que: string) {
  navigator.clipboard?.writeText(texto).then(
    () => toast.success(`${que} copiado`),
    () => toast.error('No se pudo copiar'),
  )
}

function Seccion({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <details open className="group border-b py-3 last:border-b-0">
      <summary className="cursor-pointer text-xs font-medium tracking-wide text-muted-foreground uppercase">{titulo}</summary>
      <div className="mt-2 space-y-2 text-sm">{children}</div>
    </details>
  )
}

function Dato({ k, v }: { k: string; v: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-muted-foreground">{k}</dt>
      <dd className="text-right">{v}</dd>
    </div>
  )
}

function VistaPrevia({ d }: { d: Detalle }) {
  const fallo = FALLIDOS.has(d.estado)
  return (
    <div className="space-y-4">
      {d.video ? (
        <video controls src={d.video} className="w-full rounded-lg border" />
      ) : d.pasos.length === 0 ? (
        <Vacio ilustracion="lista" titulo="Sin pasos todavía" texto="Este caso aún no se ejecutó." />
      ) : (
        <ol className="space-y-3">
          {d.pasos.map((p, i) => {
            const fallido = fallo && i === d.pasos.length - 1
            return (
              <li
                key={p.n}
                data-paso-fallido={fallido || undefined}
                className={cn('rounded-lg border p-3', fallido && 'border-danger bg-danger-soft')}
              >
                <p className="text-sm font-medium">
                  {p.n}. {p.accion} <span className="text-muted-foreground">· {p.pantalla}</span>
                </p>
                {p.observado && <p className="text-sm text-muted-foreground">{p.observado}</p>}
                {p.captura && <img src={p.captura} alt={`Captura del paso ${p.n}`} className="mt-2 max-h-72 rounded border" />}
              </li>
            )
          })}
        </ol>
      )}
      {d.falla_detalle && <Diagnostico d={d} />}
      {d.verificaciones.length > 0 && (
        <section>
          <h3 className="mb-2 text-sm font-medium">Verificaciones del oráculo</h3>
          <Table>
            <TableHeader>
              <TableRow>
                {['Verificación', 'Pantalla', 'Esperado', 'Mostrado'].map((c) => (
                  <TableHead key={c}>{c}</TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {d.verificaciones.map((v, i) => (
                <TableRow key={i}>
                  <TableCell>{v.titulo}</TableCell>
                  <TableCell>{v.pantalla}</TableCell>
                  <TableCell className="text-success">{v.esperado}</TableCell>
                  <TableCell className="text-danger">{v.obtenido}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </section>
      )}
      {d.opinion.length > 0 && (
        <section>
          <h3 className="mb-2 text-sm font-medium">Opinión de {d.persona.nombre}</h3>
          <ul className="space-y-2">
            {d.opinion.map((f, i) => (
              <li key={i} className="rounded-lg border p-3 text-sm">
                {f.cita ? <blockquote className="italic">«{f.cita}»</blockquote> : f.texto}
                <p className="text-xs text-muted-foreground">
                  {f.pantalla} · {f.severidad}
                </p>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  )
}

/** Error / Causa / Arreglo de un caso fallido, con el prompt de arreglo listo para copiar. */
function Diagnostico({ d }: { d: Detalle }) {
  const f = d.falla_detalle!
  const s = f.sugerencia
  return (
    <section className="rounded-lg border p-3">
      <Tabs defaultValue="error">
        <div className="flex items-end justify-between gap-2">
          <TabsList aria-label="Diagnóstico" className="w-auto border-b-0">
            <TabsTrigger value="error">Error</TabsTrigger>
            <TabsTrigger value="causa">Causa</TabsTrigger>
            <TabsTrigger value="arreglo">Arreglo</TabsTrigger>
          </TabsList>
          <Button size="sm" onClick={() => copiar(f.prompt, 'Prompt de arreglo')}>
            <ClipboardCopy aria-hidden="true" /> Copiar prompt de arreglo
          </Button>
        </div>
        <TabsContent value="error" className="pt-3 text-sm whitespace-pre-wrap text-danger">
          {f.error || 'El juez no dejó un motivo.'}
        </TabsContent>
        <TabsContent value="causa" className="pt-3 text-sm">
          {s ? s.causa : 'Sin sugerencia de causa para esta falla.'}
        </TabsContent>
        <TabsContent value="arreglo" className="space-y-2 pt-3 text-sm">
          {s ? (
            <>
              <Badge variant="info">
                <Sparkles aria-hidden="true" /> sugerido por IA · confianza {s.confianza}
              </Badge>
              <p>{s.cambio}</p>
              {s.archivos.length > 0 && (
                <ul className="list-disc pl-5 font-mono text-xs">
                  {s.archivos.map((a) => (
                    <li key={`${a.ruta}:${a.linea}`}>
                      {a.ruta}
                      {a.linea ? `:${a.linea}` : ''}
                    </li>
                  ))}
                </ul>
              )}
            </>
          ) : (
            'Sin sugerencia de arreglo para esta falla.'
          )}
        </TabsContent>
      </Tabs>
    </section>
  )
}

function Contenido({ d, proyecto, expandible }: { d: Detalle; proyecto: string; expandible: boolean }) {
  return (
    <div className="flex min-h-full flex-col">
      <header className="flex flex-wrap items-center gap-3 border-b px-5 py-4 pr-12">
        <span className="font-mono text-sm text-muted-foreground">{d.tc}</span>
        <h2 className="min-w-0 flex-1 truncate font-serif text-2xl">{d.nombre}</h2>
        <BadgeEstado estado={d.estado} />
        <Button variant="ghost" size="sm" onClick={() => copiar(location.href, 'Link')}>
          <Link2 aria-hidden="true" /> Copiar link
        </Button>
        {expandible && (
          <Button asChild variant="ghost" size="sm">
            <Link to="/proyectos/$proyecto/casos/$tc" params={{ proyecto, tc: d.tc }}>
              <Maximize2 aria-hidden="true" /> Expandir
            </Link>
          </Button>
        )}
      </header>
      <div className="grid flex-1 md:grid-cols-[18rem_1fr]">
        <aside className="border-b px-5 md:border-r md:border-b-0">
          <Seccion titulo="Básico">
            <dl className="space-y-2">
              <Dato k="Prioridad" v={<Prioridad nivel={d.prioridad} />} />
              <Dato
                k="Persona"
                v={
                  <span className="inline-flex items-center gap-2">
                    <Avatar nombre={d.persona.nombre} className="size-6" />
                    {d.persona.nombre}
                  </span>
                }
              />
              <Dato k="Idioma" v={d.persona.idioma || '—'} />
              <Dato k="Destreza" v={d.persona.destreza ? `${d.persona.destreza} de 5` : '—'} />
              <Dato k="Caso de uso" v={d.caso_de_uso} />
              {d.fecha && <Dato k="Última ejecución" v={hace(d.fecha)} />}
            </dl>
          </Seccion>
          <Seccion titulo="Plan">
            <p>
              <strong>Objetivo:</strong> {d.objetivo}
            </p>
            <p>
              <strong>Criterio de éxito:</strong> {d.criterio_exito}
            </p>
            {d.pasos.length > 0 && (
              <ol className="list-decimal space-y-1 pl-5 text-muted-foreground">
                {d.pasos.map((p) => (
                  <li key={p.n}>{p.accion}</li>
                ))}
              </ol>
            )}
          </Seccion>
          <Seccion titulo="Ajustes">
            <dl className="space-y-2">
              {Object.entries(d.ajustes).map(([k, v]) => (
                <Dato key={k} k={k} v={v} />
              ))}
            </dl>
          </Seccion>
        </aside>
        <Tabs defaultValue="vista" className="min-w-0 px-5 py-3">
          <TabsList aria-label="Detalle del caso">
            <TabsTrigger value="vista">Vista previa</TabsTrigger>
            <TabsTrigger value="codigo">Código</TabsTrigger>
            <TabsTrigger value="historial">Historial</TabsTrigger>
          </TabsList>
          <TabsContent value="vista" className="pt-4">
            <VistaPrevia d={d} />
          </TabsContent>
          <TabsContent value="codigo" className="pt-4">
            {d.codigo ? (
              <pre className="overflow-auto rounded-lg bg-muted p-3 text-xs" data-lenguaje={d.lenguaje_codigo}>
                {d.codigo}
              </pre>
            ) : (
              <Vacio
                ilustracion="carpeta"
                titulo="Todavía no se exportó"
                texto="Cuando el caso se exporte como test de Playwright o Patrol, aparece aquí."
              />
            )}
          </TabsContent>
          <TabsContent value="historial" className="pt-4">
            {d.historial.length === 0 ? (
              <Vacio ilustracion="lista" titulo="Sin ejecuciones todavía" />
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    {['Estado', 'Error', 'Fecha', ''].map((c) => (
                      <TableHead key={c}>{c}</TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {d.historial.map((h) => (
                    <TableRow key={h.ejecucion_id}>
                      <TableCell>
                        <BadgeEstado estado={h.estado} />
                      </TableCell>
                      <TableCell className="max-w-80 truncate text-danger">{h.error}</TableCell>
                      <TableCell className="whitespace-nowrap text-muted-foreground">{hace(h.fecha)}</TableCell>
                      <TableCell>
                        <Link
                          to="/proyectos/$proyecto/ejecuciones/$id"
                          params={{ proyecto, id: h.ejecucion_id }}
                          className="text-sm underline"
                        >
                          Ver ejecución
                        </Link>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </TabsContent>
        </Tabs>
      </div>
    </div>
  )
}

/** Detalle de un caso: en el sheet de la lista (`expandible`) o a pantalla completa. */
export function DetalleCaso({ proyecto, tc, expandible = false }: { proyecto: string; tc: string; expandible?: boolean }) {
  const q = useCaso(proyecto, tc)
  if (q.isPending) return <Skeleton className="m-5 h-60" />
  if (q.isError) return <Vacio icono={TriangleAlert} titulo={`El caso ${tc} no existe`} />
  return <Contenido d={q.data} proyecto={proyecto} expandible={expandible} />
}
