import { Link, useNavigate, useParams, useSearch } from '@tanstack/react-router'
import { TriangleAlert } from 'lucide-react'
import { type ReactNode, useState } from 'react'
import { toast } from 'sonner'

import { EncabezadoPagina } from '@/components/layout/EncabezadoPagina'
import { Vacio } from '@/components/layout/Vacio'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Sheet, SheetContent, SheetDescription, SheetTitle } from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { hace } from '@/features/casos/api'
import { DetalleCaso } from '@/features/casos/DetalleCaso'
import { type Insights, useInsights } from './api'

export const validarBusquedaInsights = (s: Record<string, unknown>): { caso?: string } => ({
  caso: typeof s.caso === 'string' && s.caso ? s.caso : undefined,
})

const pct = (n: number, t: number) => (t ? Math.round((100 * n) / t) : 0)

function Bloque({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <section className="mt-8">
      <h2 className="mb-3 font-serif text-xl tracking-tight">{titulo}</h2>
      {children}
    </section>
  )
}

function Kpi({ titulo, valor, pie }: { titulo: string; valor: ReactNode; pie?: ReactNode }) {
  return (
    <Card role="group" aria-label={titulo} className="gap-2">
      <CardHeader className="pb-0">
        <CardTitle className="text-sm font-medium tracking-normal text-muted-foreground">{titulo}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="text-3xl font-semibold tabular-nums">{valor}</div>
        {pie && <div className="mt-1 text-xs text-muted-foreground">{pie}</div>}
      </CardContent>
    </Card>
  )
}

/** Dona sin librería: un conic-gradient con una leyenda. */
function Dona({ titulo, partes }: { titulo: string; partes: { etiqueta: string; valor: number; color: string }[] }) {
  const total = partes.reduce((n, p) => n + p.valor, 0)
  let acum = 0
  const tramos = partes.map((p) => {
    const t = `${p.color} ${acum}% ${(acum += pct(p.valor, total))}%`
    return t
  })
  return (
    <figure className="flex items-center gap-4">
      <div
        role="img"
        aria-label={`${titulo}: ${partes.map((p) => `${p.etiqueta} ${p.valor}`).join(', ')}`}
        className="size-24 shrink-0 rounded-full"
        style={{ background: total ? `conic-gradient(${tramos.join(',')})` : 'hsl(var(--muted))' }}
      >
        <div className="m-6 size-12 rounded-full bg-card" />
      </div>
      <figcaption className="text-sm">
        <p className="mb-1 font-medium">{titulo}</p>
        {partes.map((p) => (
          <p key={p.etiqueta} className="flex items-center gap-1.5 text-muted-foreground">
            <span className="size-2 rounded-full" style={{ background: p.color }} />
            {p.etiqueta} <span className="tabular-nums">{p.valor}</span>
          </p>
        ))}
      </figcaption>
    </figure>
  )
}

function Tendencia({ puntos }: { puntos: Insights['tendencia'] }) {
  if (puntos.length < 2) return <p className="text-sm text-muted-foreground">La tendencia necesita una segunda corrida</p>
  const x = (i: number) => (i / (puntos.length - 1)) * 300
  return (
    <svg role="img" aria-label="Tasa de éxito por corrida" viewBox="0 0 300 60" className="h-20 w-full max-w-xl">
      <polyline
        fill="none"
        stroke="hsl(var(--primary))"
        strokeWidth="2"
        points={puntos.map((p, i) => `${x(i)},${58 - p.tasa * 56}`).join(' ')}
      />
    </svg>
  )
}

function Chips({ casos, abrir }: { casos: string[]; abrir: (tc: string) => void }) {
  return (
    <span className="flex flex-wrap gap-1">
      {casos.map((tc) => (
        <button
          key={tc}
          type="button"
          onClick={() => abrir(tc)}
          className="rounded bg-muted px-1.5 font-mono text-xs hover:bg-accent"
        >
          {tc}
        </button>
      ))}
    </span>
  )
}

const FILTROS = { todos: 'Todos', cubierto: 'Cubiertos', planeado: 'Planeados', brecha: 'Brecha' } as const
const PUNTO = { paso: 'bg-success', fallo: 'bg-danger', no_concluyente: 'bg-danger', bloqueado: 'bg-warning', planeado: 'bg-muted-foreground/40', corriendo: 'bg-primary' }

function Cobertura({ filas }: { filas: Insights['cobertura'] }) {
  const [filtro, setFiltro] = useState<keyof typeof FILTROS>('todos')
  const visibles = filas.filter((f) => filtro === 'todos' || f.estado === filtro)
  const suma = (k: 'pasaron' | 'fallaron' | 'casos') => filas.reduce((n, f) => n + f[k], 0)
  return (
    <div className="mt-6">
      <h3 className="mb-3 font-medium">Cobertura por caso de uso</h3>
      <div className="mb-4 flex flex-wrap gap-8">
        <Dona
          titulo="Casos por caso de uso"
          partes={filas.map((f, i) => ({ etiqueta: f.caso_de_uso, valor: f.casos, color: `hsl(${(i * 67) % 360} 55% 55%)` }))}
        />
        <Dona
          titulo="Pasaron y fallaron"
          partes={[
            { etiqueta: 'Pasaron', valor: suma('pasaron'), color: 'hsl(var(--success))' },
            { etiqueta: 'Fallaron', valor: suma('casos') - suma('pasaron'), color: 'hsl(var(--danger))' },
          ]}
        />
      </div>
      <Tabs value={filtro} onValueChange={(v) => setFiltro(v as keyof typeof FILTROS)}>
        <TabsList aria-label="Filtrar cobertura">
          {Object.entries(FILTROS).map(([k, t]) => (
            <TabsTrigger key={k} value={k}>
              {t}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
      <Table className="mt-3">
        <TableHeader>
          <TableRow>
            {['Caso de uso', 'Últimos resultados', 'Casos', 'Pasaron', 'Fallaron', 'Bloqueados', '%', 'Última corrida'].map((h) => (
              <TableHead key={h}>{h}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {visibles.map((f) => (
            <TableRow key={f.caso_de_uso} data-uso={f.caso_de_uso}>
              <TableCell className="font-medium">{f.caso_de_uso}</TableCell>
              <TableCell>
                <span className="flex gap-1">
                  {f.ultimos.map((e, i) => (
                    <span key={i} title={e} className={`size-2.5 rounded-full ${PUNTO[e]}`} />
                  ))}
                </span>
              </TableCell>
              <TableCell>{f.casos}</TableCell>
              <TableCell>{f.pasaron}</TableCell>
              <TableCell>{f.fallaron}</TableCell>
              <TableCell>{f.bloqueados}</TableCell>
              <TableCell>{f.porcentaje}%</TableCell>
              <TableCell>{f.ultima ? hace(f.ultima) : '—'}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  )
}

function Contenido({ proyecto, i, abrir }: { proyecto: string; i: Insights; abrir: (tc: string) => void }) {
  const copiar = () =>
    navigator.clipboard?.writeText(i.prompt).then(
      () => toast.success('Prompt de arreglo copiado'),
      () => toast.error('No se pudo copiar'),
    )
  const costo = i.tendencia.at(-1)?.costo_usd ?? 0
  return (
    <>
      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-3">
          <p className="font-medium">
            {i.casos_fallaron ? `${i.casos_fallaron} casos fallaron en la última corrida` : 'Ningún caso falló en la última corrida'}
          </p>
          <div className="flex gap-2">
            {i.casos_fallaron > 0 && <Button onClick={copiar}>Copiar prompt de arreglo</Button>}
            <Button variant="outline" asChild>
              <Link to="/proyectos/$proyecto/github" params={{ proyecto }}>
                Instalar la acción de GitHub
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>

      <Bloque titulo="Última corrida">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Kpi titulo="Tasa de éxito" valor={`${pct(i.pasaron, i.total)}%`} pie={`${i.pasaron} de ${i.total} casos`} />
          <Kpi titulo="Issues abiertos" valor={i.abiertos} />
          <Kpi titulo="Arreglados" valor={i.arreglados} />
          <Kpi
            titulo="Regresiones"
            valor={i.regresiones.length}
            pie={i.regresiones.map((r) => `${r.tc} volvió en ${r.ref}`).join(' · ')}
          />
        </div>
        <div className="mt-4">
          <Tendencia puntos={i.tendencia} />
        </div>
      </Bloque>

      <Bloque titulo="Issues para arreglar, agrupados por causa">
        {i.issues.length === 0 ? (
          <p className="text-sm text-muted-foreground">Sin issues abiertos.</p>
        ) : (
          <ul className="space-y-2">
            {i.issues.map((x) => (
              <li key={x.huella} data-huella={x.huella} className="rounded-lg border bg-card p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{x.titulo}</span>
                  <span className="text-sm text-muted-foreground">{x.ruta}</span>
                  <span className="rounded bg-muted px-1.5 text-xs">{x.gravedad}</span>
                  <span className="ml-auto text-sm tabular-nums">{x.casos.length} casos</span>
                </div>
                <div className="mt-2">
                  <Chips casos={x.casos} abrir={abrir} />
                </div>
              </li>
            ))}
          </ul>
        )}
      </Bloque>

      <Bloque titulo="Lo que dogfood suma">
        <div className="grid gap-4 lg:grid-cols-3">
          <Card>
            <CardHeader>
              <CardTitle>Fricción por pantalla</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              {i.friccion.length === 0 && <p className="text-muted-foreground">Sin fricción registrada.</p>}
              {i.friccion.map((f) => (
                <div key={f.pantalla}>
                  <p className="font-medium">
                    {f.pantalla} <span className="text-muted-foreground tabular-nums">· {f.n}</span>
                  </p>
                  {f.citas.map((c, n) => (
                    <blockquote key={n} className="border-l-2 pl-2 text-muted-foreground">
                      «{c}»
                    </blockquote>
                  ))}
                </div>
              ))}
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Números verificados por el oráculo</CardTitle>
            </CardHeader>
            <CardContent>
              <Dona
                titulo="Correctos contra equivocados"
                partes={[
                  { etiqueta: 'Correctos', valor: i.oraculo.correctas, color: 'hsl(var(--success))' },
                  { etiqueta: 'Equivocados', valor: i.oraculo.equivocadas, color: 'hsl(var(--danger))' },
                ]}
              />
            </CardContent>
          </Card>
          <Card>
            <CardHeader>
              <CardTitle>Costo por corrida</CardTitle>
            </CardHeader>
            <CardContent className="text-sm">
              <p className="text-2xl font-semibold tabular-nums">US$ {costo.toFixed(2)}</p>
              <p className="text-muted-foreground">en la última corrida</p>
            </CardContent>
          </Card>
        </div>
        <Cobertura filas={i.cobertura} />
      </Bloque>
    </>
  )
}

/** Insights del proyecto: qué arreglar primero, tendencia y cobertura. El caso se abre en un sheet (`?caso=`). */
export function PantallaInsights() {
  const { proyecto } = useParams({ strict: false }) as { proyecto: string }
  const { caso } = useSearch({ strict: false }) as { caso?: string }
  const navigate = useNavigate()
  const q = useInsights(proyecto)
  const abrir = (c?: string) => navigate({ to: '.', search: ((s: object) => ({ ...s, caso: c })) as never })
  return (
    <>
      <EncabezadoPagina titulo="Insights" subtitulo="Qué arreglar primero: issues agrupados por causa, tendencia y cobertura por caso de uso." />
      {q.isPending ? (
        <Skeleton className="h-40 w-full" />
      ) : q.isError ? (
        <Vacio icono={TriangleAlert} titulo="No se pudieron cargar los insights" texto="Revisa que el proyecto exista." />
      ) : !q.data.corrida_id ? (
        <Vacio ilustracion="grafico" titulo="Todavía no hay insights" texto="Aparecen cuando el proyecto tenga corridas con resultados." />
      ) : (
        <Contenido proyecto={proyecto} i={q.data} abrir={abrir} />
      )}
      <Sheet open={!!caso} onOpenChange={(a) => !a && abrir(undefined)}>
        <SheetContent side="right" className="w-[min(72rem,95vw)] max-w-none overflow-y-auto p-0">
          <SheetTitle className="sr-only">Detalle del caso {caso}</SheetTitle>
          <SheetDescription className="sr-only">Plan, vista previa, código e historial del caso.</SheetDescription>
          {caso && <DetalleCaso proyecto={proyecto} tc={caso} expandible />}
        </SheetContent>
      </Sheet>
    </>
  )
}
