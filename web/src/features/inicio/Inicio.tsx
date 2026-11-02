import { Link } from '@tanstack/react-router'
import { Check, Circle } from 'lucide-react'

import { EncabezadoPagina } from '@/components/layout/EncabezadoPagina'
import { Vacio } from '@/components/layout/Vacio'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Table, TableBody, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { FilaProyecto } from '@/features/proyectos/ListaProyectos'
import { type ProyectoLista, useProyectos } from '@/features/proyectos/api'

/** Cada paso sale de los datos reales de los proyectos. */
export function primerosPasos(ps: ProyectoLista[]) {
  return [
    { id: 'proyecto', texto: 'Crear un proyecto', hecho: ps.length > 0, to: '/proyectos/nuevo' },
    { id: 'corrida', texto: 'Hacer la primera corrida', hecho: ps.some((p) => p.ultimos.corrida_id), to: '/proyectos' },
    { id: 'slack', texto: 'Conectar Slack', hecho: ps.some((p) => p.notificaciones.slack), to: '/proyectos' },
    {
      id: 'github',
      texto: 'Conectar GitHub',
      hecho: ps.some((p) => p.notificaciones.issues_github && p.notificaciones.repo !== ''),
      to: '/proyectos',
    },
  ] as const
}

export function Inicio() {
  const { data } = useProyectos()
  const ps = data ?? []
  const pasos = primerosPasos(ps)
  const hechas = pasos.filter((p) => p.hecho).length
  const recientes = [...ps]
    .sort((a, b) => (b.ultimos.ultima_actividad ?? '').localeCompare(a.ultimos.ultima_actividad ?? ''))
    .slice(0, 5)

  return (
    <>
      <EncabezadoPagina titulo="Inicio" subtitulo="Cómo les va a tus personas en todos los proyectos." />
      <Card className="mb-6">
        <CardContent className="flex flex-wrap items-center gap-6 p-6">
          <svg viewBox="0 0 80 80" aria-hidden="true" className="size-24 fill-none stroke-muted-foreground" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="40" cy="26" r="10" />
            <path d="M20 66c0-12 9-20 20-20s20 8 20 20M60 14l4 4 8-8" />
          </svg>
          <div className="flex-1">
            <h2 className="font-serif text-2xl">Te damos la bienvenida a dogfood</h2>
            <p className="text-muted-foreground">Personas agénticas usan tu app y te cuentan dónde se traban.</p>
          </div>
          <div className="flex gap-2">
            <Button asChild><Link to="/proyectos">Ver proyectos</Link></Button>
            <Button asChild variant="outline"><Link to="/ayuda">Ver ayuda</Link></Button>
          </div>
        </CardContent>
      </Card>

      <Card className="mb-6" data-bloque="primeros-pasos">
        <CardHeader>
          <CardTitle>Primeros pasos</CardTitle>
          <p className="text-sm text-muted-foreground">{hechas} de {pasos.length} hechas</p>
          <div
            role="progressbar"
            aria-label="Primeros pasos"
            aria-valuemin={0}
            aria-valuemax={pasos.length}
            aria-valuenow={hechas}
            className="h-2 overflow-hidden rounded-full bg-muted"
          >
            <div className="h-full bg-primary" style={{ width: `${(hechas / pasos.length) * 100}%` }} />
          </div>
        </CardHeader>
        <CardContent>
          <ul className="space-y-2">
            {pasos.map((p) => (
              <li key={p.id} data-paso={p.id} data-hecho={p.hecho} className="flex items-center gap-2">
                {p.hecho ? <Check aria-hidden="true" className="size-4 text-success" /> : <Circle aria-hidden="true" className="size-4 text-muted-foreground" />}
                <Link to={p.to} className={p.hecho ? 'text-muted-foreground line-through' : 'hover:underline'}>{p.texto}</Link>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      <h2 className="mb-2 font-serif text-xl">Proyectos recientes</h2>
      {recientes.length === 0 ? (
        <Vacio ilustracion="carpeta" titulo="Todavía no hay proyectos" className="mb-6" />
      ) : (
        <div className="mb-6 rounded-xl border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nombre</TableHead>
                <TableHead>Últimos resultados</TableHead>
                <TableHead>Última actividad</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>{recientes.map((p) => <FilaProyecto key={p.slug} p={p} />)}</TableBody>
          </Table>
        </div>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <h2 className="mb-2 font-serif text-xl">Suites</h2>
          <Vacio ilustracion="lista" titulo="Todavía no hay suites" texto="Una suite junta casos de prueba para correrlos de una vez." />
        </div>
        <div>
          <h2 className="mb-2 font-serif text-xl">Programaciones</h2>
          <Vacio ilustracion="calendario" titulo="Todavía no hay programaciones" texto="Corre una suite cada hora, a diario o cada semana." />
        </div>
      </div>
    </>
  )
}
