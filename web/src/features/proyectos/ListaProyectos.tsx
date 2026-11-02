import { Link } from '@tanstack/react-router'
import { Plus } from 'lucide-react'
import { useMemo, useState } from 'react'

import { EncabezadoPagina } from '@/components/layout/EncabezadoPagina'
import { Vacio } from '@/components/layout/Vacio'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { ETIQUETA_TIPO, type ProyectoLista, useProyectos } from './api'

const PAGINA = 10
const TABS = [
  ['todos', 'Todos'],
  ['web', 'Web'],
  ['android', 'Android'],
  ['ios', 'iOS'],
] as const
const ORDENES = { reciente: 'Última actividad', nombre: 'Nombre', creado: 'Creado' } as const

export const fecha = (s: string | null) => (s ? new Date(s).toLocaleDateString('es') : '—')

export function Resultados({ p }: { p: ProyectoLista }) {
  const { pasaron, fallaron } = p.ultimos
  if (!p.ultimos.corrida_id) return <span className="text-muted-foreground">Sin corridas</span>
  return (
    <span className="flex gap-1">
      <Badge variant="success" aria-label={`${pasaron} pasaron`}>{pasaron}</Badge>
      <Badge variant="danger" aria-label={`${fallaron} fallaron`}>{fallaron}</Badge>
    </span>
  )
}

export function FilaProyecto({ p, completa }: { p: ProyectoLista; completa?: boolean }) {
  return (
    <TableRow data-proyecto={p.slug}>
      <TableCell className="font-medium">
        <Link to="/proyectos/$proyecto/casos" params={{ proyecto: p.slug }} className="hover:underline">
          {p.nombre}
        </Link>
      </TableCell>
      <TableCell><Resultados p={p} /></TableCell>
      <TableCell>{fecha(p.ultimos.ultima_actividad)}</TableCell>
      {completa && (
        <>
          <TableCell>{fecha(p.creado)}</TableCell>
          <TableCell><Badge variant="neutral">{ETIQUETA_TIPO[p.tipo]}</Badge></TableCell>
          <TableCell>{p.origen ?? 'CLI'}</TableCell>
        </>
      )}
    </TableRow>
  )
}

export function ListaProyectos() {
  const { data, isPending, isError } = useProyectos()
  const [tab, setTab] = useState<(typeof TABS)[number][0]>('todos')
  const [q, setQ] = useState('')
  const [orden, setOrden] = useState<keyof typeof ORDENES>('reciente')
  const [pagina, setPagina] = useState(0)

  const filas = useMemo(() => {
    const f = (data ?? []).filter(
      (p) =>
        (tab === 'todos' || ETIQUETA_TIPO[p.tipo].toLowerCase() === tab) &&
        p.nombre.toLowerCase().includes(q.trim().toLowerCase()),
    )
    const clave = (p: ProyectoLista) =>
      orden === 'nombre' ? p.nombre : ((orden === 'creado' ? p.creado : p.ultimos.ultima_actividad) ?? '')
    return f.sort((a, b) => (orden === 'nombre' ? clave(a).localeCompare(clave(b)) : clave(b).localeCompare(clave(a))))
  }, [data, tab, q, orden])
  const paginas = Math.max(1, Math.ceil(filas.length / PAGINA))
  const actual = Math.min(pagina, paginas - 1)

  return (
    <>
      <EncabezadoPagina
        titulo="Proyectos"
        subtitulo="Cada proyecto es una app que dogfood prueba con sus personas."
        acciones={
          <Button asChild>
            <Link to="/proyectos/nuevo"><Plus aria-hidden="true" />Proyecto nuevo</Link>
          </Button>
        }
      />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Tabs value={tab} onValueChange={(v) => { setTab(v as typeof tab); setPagina(0) }}>
          <TabsList>
            {TABS.map(([v, t]) => <TabsTrigger key={v} value={v}>{t}</TabsTrigger>)}
          </TabsList>
        </Tabs>
        <Input
          aria-label="Buscar proyecto"
          placeholder="Buscar proyecto"
          className="max-w-xs"
          value={q}
          onChange={(e) => { setQ(e.target.value); setPagina(0) }}
        />
        <label className="ml-auto flex items-center gap-2 text-sm text-muted-foreground">
          Ordenar por
          <select
            aria-label="Ordenar por"
            className="h-9 rounded-md border bg-background px-2 text-foreground"
            value={orden}
            onChange={(e) => setOrden(e.target.value as keyof typeof ORDENES)}
          >
            {Object.entries(ORDENES).map(([v, t]) => <option key={v} value={v}>{t}</option>)}
          </select>
        </label>
      </div>
      {isPending ? (
        <Skeleton className="h-40 w-full" />
      ) : isError ? (
        <Vacio error titulo="No se pudieron cargar los proyectos" />
      ) : filas.length === 0 ? (
        <Vacio ilustracion="carpeta" titulo="Sin proyectos" texto="Ningún proyecto coincide con el filtro." />
      ) : (
        <div className="rounded-xl border bg-card">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Nombre</TableHead>
                <TableHead>Últimos resultados</TableHead>
                <TableHead>Última actividad</TableHead>
                <TableHead>Creado</TableHead>
                <TableHead>Tipo</TableHead>
                <TableHead>Origen</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filas.slice(actual * PAGINA, (actual + 1) * PAGINA).map((p) => (
                <FilaProyecto key={p.slug} p={p} completa />
              ))}
            </TableBody>
          </Table>
          <div className="flex items-center justify-end gap-2 border-t p-2 text-sm text-muted-foreground">
            Página {actual + 1} de {paginas}
            <Button variant="outline" size="sm" disabled={actual === 0} onClick={() => setPagina(actual - 1)}>
              Anterior
            </Button>
            <Button variant="outline" size="sm" disabled={actual >= paginas - 1} onClick={() => setPagina(actual + 1)}>
              Siguiente
            </Button>
          </div>
        </div>
      )}
    </>
  )
}
