import { useQuery } from '@tanstack/react-query'
import { Link, useNavigate } from '@tanstack/react-router'
import {
  type ColumnDef,
  type ColumnFiltersState,
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  type SortingState,
  useReactTable,
  type VisibilityState,
} from '@tanstack/react-table'
import { ArrowDown, ArrowUp, ArrowUpDown, BookOpen, Columns3, PlayCircle, TriangleAlert } from 'lucide-react'
import { useMemo, useState } from 'react'

import { cliente } from '@/api/cliente'
import type { components } from '@/api/schema'
import { Vacio } from '@/components/layout/Vacio'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuCheckboxItem,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Input } from '@/components/ui/input'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { BadgeResultado, duracion, fecha, usd } from './comun'
import { useEjecuciones } from './kpis'

export const FILTROS = ['recorrido', 'resultado', 'version', 'persona', 'driver', 'motor'] as const
export type Filtros = Partial<Record<(typeof FILTROS)[number], string>>
export type Fila = components['schemas']['FilaEjecucion']

/** Para `validateSearch` de la ruta: solo claves conocidas con texto no vacío. */
export function validarFiltros(s: Record<string, unknown>): Filtros {
  const f: Filtros = {}
  for (const k of FILTROS) if (typeof s[k] === 'string' && s[k]) f[k] = s[k] as string
  return f
}

const persona = (f: Fila) => `${f.persona_nombre ?? f.persona_id} (${f.persona_idioma ?? '?'})`

function columnas(etiquetas: Record<string, string>): ColumnDef<Fila>[] {
  const texto = (id: keyof Fila, header: string): ColumnDef<Fila> => ({ accessorKey: id, header })
  const num = (id: keyof Fila, header: string, fmt: (n: number) => string = String): ColumnDef<Fila> => ({
    accessorKey: id,
    header,
    cell: (c) => <span className="tabular-nums">{fmt(c.getValue<number>())}</span>,
  })
  return [
    {
      accessorKey: 'corrida_id',
      header: 'Corrida',
      cell: ({ row }) => (
        <Link
          to="/corridas/$id"
          params={{ id: row.original.corrida_id }}
          onClick={(e) => e.stopPropagation()}
          className="font-medium underline-offset-4 hover:underline"
        >
          {row.original.corrida_id}
        </Link>
      ),
    },
    { accessorKey: 'fecha', header: 'Fecha', cell: (c) => fecha(c.getValue<string>()) },
    texto('version', 'Versión'),
    { id: 'persona', accessorFn: persona, header: 'Persona' },
    texto('escenario_id', 'Escenario'),
    texto('driver', 'Driver'),
    texto('motor', 'Motor'),
    texto('backend', 'Backend'),
    texto('modelo', 'Modelo'),
    {
      accessorKey: 'resultado',
      header: 'Resultado',
      cell: (c) => <BadgeResultado resultado={c.getValue<string>()} etiqueta={etiquetas[c.getValue<string>()]} />,
    },
    num('duracion_s', 'Duración', duracion),
    num('pasos', 'Pasos'),
    num('tokens', 'Tokens'),
    num('capturas', 'Capturas'),
    num('costo_usd', 'Costo', usd),
    num('costo_equivalente_usd', 'Costo equiv.', usd),
  ]
}

/** Columnas que arrancan ocultas (se muestran desde «Columnas»). */
const OCULTAS: VisibilityState = { backend: false, modelo: false, tokens: false, capturas: false, costo_equivalente_usd: false }

export function TablaEjecuciones({ filtros }: { filtros: Filtros }) {
  const navigate = useNavigate()
  const ejecuciones = useEjecuciones(filtros)
  const etiquetas = useQuery({
    queryKey: ['etiquetas'],
    queryFn: async () => (await cliente.GET('/api/etiquetas')).data ?? {},
  })
  const [sorting, setSorting] = useState<SortingState>([{ id: 'fecha', desc: true }])
  const [columnFilters, setColumnFilters] = useState<ColumnFiltersState>([])
  const [columnVisibility, setColumnVisibility] = useState<VisibilityState>(OCULTAS)
  const columns = useMemo(() => columnas(etiquetas.data ?? {}), [etiquetas.data])

  // eslint-disable-next-line react-hooks/incompatible-library -- TanStack Table no es memoizable por el compilador
  const tabla = useReactTable({
    data: ejecuciones.data ?? [],
    columns,
    state: { sorting, columnFilters, columnVisibility },
    onSortingChange: setSorting,
    onColumnFiltersChange: setColumnFilters,
    onColumnVisibilityChange: setColumnVisibility,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
    initialState: { pagination: { pageSize: 20 } },
  })

  if (ejecuciones.isError)
    return (
      <Vacio
        error
        icono={TriangleAlert}
        titulo="No se pudieron cargar las ejecuciones"
        texto="Revisa que el panel esté corriendo y vuelve a intentar."
        accion={<Button onClick={() => ejecuciones.refetch()}>Reintentar</Button>}
      />
    )
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
      <Vacio
        icono={PlayCircle}
        titulo="Sin ejecuciones"
        texto="Todavía no hay corridas con estos filtros."
        accion={
          <Button asChild variant="outline">
            <Link to="/ayuda/$slug" params={{ slug: 'primera-corrida' }}>
              <BookOpen aria-hidden="true" />
              Cómo correr dogfood
            </Link>
          </Button>
        }
      />
    )

  const filtroPersona = tabla.getColumn('persona')
  const { pageIndex } = tabla.getState().pagination
  const filas = tabla.getRowModel().rows
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Input
          aria-label="Buscar por persona"
          placeholder="Buscar por persona…"
          value={(filtroPersona?.getFilterValue() as string) ?? ''}
          onChange={(e) => filtroPersona?.setFilterValue(e.target.value)}
          className="h-9 max-w-xs"
        />
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="outline" size="sm" className="ml-auto">
              <Columns3 aria-hidden="true" />
              Columnas
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <DropdownMenuLabel>Columnas visibles</DropdownMenuLabel>
            <DropdownMenuSeparator />
            {tabla.getAllLeafColumns().map((c) => (
              <DropdownMenuCheckboxItem
                key={c.id}
                checked={c.getIsVisible()}
                onCheckedChange={(v) => c.toggleVisibility(!!v)}
                onSelect={(e) => e.preventDefault()}
              >
                {String(c.columnDef.header)}
              </DropdownMenuCheckboxItem>
            ))}
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
      <div className="overflow-hidden rounded-xl border bg-card">
        <Table>
          <TableHeader>
            {tabla.getHeaderGroups().map((g) => (
              <TableRow key={g.id}>
                {g.headers.map((h) => {
                  const orden = h.column.getIsSorted()
                  const Icono = orden === 'asc' ? ArrowUp : orden === 'desc' ? ArrowDown : ArrowUpDown
                  return (
                    <TableHead
                      key={h.id}
                      aria-sort={orden === 'asc' ? 'ascending' : orden === 'desc' ? 'descending' : undefined}
                    >
                      <button
                        type="button"
                        onClick={h.column.getToggleSortingHandler()}
                        className="-mx-1 inline-flex items-center gap-1 rounded px-1 py-0.5 whitespace-nowrap hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                      >
                        {flexRender(h.column.columnDef.header, h.getContext())}
                        <Icono aria-hidden="true" className={orden ? 'size-3.5' : 'size-3.5 opacity-40'} />
                      </button>
                    </TableHead>
                  )
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {filas.length ? (
              filas.map((r) => (
                <TableRow
                  key={r.id}
                  className="cursor-pointer"
                  onClick={() => navigate({ to: '/ejecuciones/$id', params: { id: r.original.id } })}
                >
                  {r.getVisibleCells().map((c) => (
                    <TableCell key={c.id} className="whitespace-nowrap">
                      {flexRender(c.column.columnDef.cell, c.getContext())}
                    </TableCell>
                  ))}
                </TableRow>
              ))
            ) : (
              <TableRow>
                <TableCell colSpan={tabla.getVisibleLeafColumns().length} className="h-24 text-center text-muted-foreground">
                  Ninguna persona coincide con la búsqueda.
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </div>
      <div className="flex items-center justify-between gap-2 text-sm text-muted-foreground">
        <span>
          {tabla.getFilteredRowModel().rows.length} ejecuciones · página {pageIndex + 1} de {Math.max(tabla.getPageCount(), 1)}
        </span>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => tabla.previousPage()} disabled={!tabla.getCanPreviousPage()}>
            Anterior
          </Button>
          <Button variant="outline" size="sm" onClick={() => tabla.nextPage()} disabled={!tabla.getCanNextPage()}>
            Siguiente
          </Button>
        </div>
      </div>
    </div>
  )
}
