import { ChevronLeft, ChevronRight } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export type Nivel = 'alta' | 'media' | 'baja'
const BARRAS: Record<Nivel, number> = { alta: 3, media: 2, baja: 1 }

/** Prioridad con un ícono de tres barras: alta llena las tres, baja solo una. */
export function Prioridad({ nivel, conTexto = true }: { nivel: Nivel; conTexto?: boolean }) {
  const llenas = BARRAS[nivel]
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground" data-prioridad={nivel}>
      <svg viewBox="0 0 12 12" className="size-3.5" aria-hidden="true">
        {[0, 1, 2].map((i) => (
          <rect
            key={i}
            x={i * 4.5}
            y={8 - i * 3}
            width="3"
            height={4 + i * 3}
            rx="0.75"
            className={i < llenas ? 'fill-foreground' : 'fill-border'}
          />
        ))}
      </svg>
      {conTexto ? <span className="capitalize">{nivel}</span> : <span className="sr-only">Prioridad {nivel}</span>}
    </span>
  )
}

const iniciales = (nombre: string) =>
  nombre
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? '')
    .join('') || '?'

/** Avatar de una persona: sus iniciales sobre un tono estable derivado del nombre. */
export function Avatar({ nombre, className }: { nombre: string; className?: string }) {
  const tono = [...nombre].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 360, 0)
  return (
    <span
      title={nombre}
      aria-label={nombre}
      role="img"
      className={cn('inline-grid size-7 shrink-0 place-items-center rounded-full text-[11px] font-semibold', className)}
      style={{ backgroundColor: `hsl(${tono} 45% 90%)`, color: `hsl(${tono} 45% 28%)` }}
    >
      {iniciales(nombre)}
    </span>
  )
}

/** «25 filas ▾ · ‹ Anterior 1 Siguiente ›». `pagina` empieza en 1. */
export function Paginacion({
  pagina,
  total,
  porPagina,
  onPagina,
  onPorPagina,
}: {
  pagina: number
  total: number
  porPagina: number
  onPagina: (p: number) => void
  onPorPagina?: (n: number) => void
}) {
  const paginas = Math.max(1, Math.ceil(total / porPagina))
  return (
    <nav aria-label="Paginación" className="flex flex-wrap items-center justify-end gap-3 py-3 text-sm text-muted-foreground">
      {onPorPagina && (
        <select
          aria-label="Filas por página"
          value={porPagina}
          onChange={(e) => onPorPagina(Number(e.target.value))}
          className="h-8 rounded-md border bg-background px-2 text-foreground"
        >
          {[10, 25, 50, 100].map((n) => (
            <option key={n} value={n}>
              {n} filas
            </option>
          ))}
        </select>
      )}
      <Button variant="ghost" size="sm" disabled={pagina <= 1} onClick={() => onPagina(pagina - 1)}>
        <ChevronLeft aria-hidden="true" /> Anterior
      </Button>
      <span className="tabular-nums" aria-current="page">
        {pagina} de {paginas}
      </span>
      <Button variant="ghost" size="sm" disabled={pagina >= paginas} onClick={() => onPagina(pagina + 1)}>
        Siguiente <ChevronRight aria-hidden="true" />
      </Button>
    </nav>
  )
}

export interface Segmento {
  valor: number
  etiqueta: string
  /** Clase de fondo, p. ej. `bg-success`. */
  clase: string
}

/** Barra horizontal apilada (verde/rojo de los grupos de casos). */
export function BarraApilada({ segmentos, className }: { segmentos: Segmento[]; className?: string }) {
  const total = segmentos.reduce((n, s) => n + s.valor, 0)
  const resumen = segmentos.map((s) => `${s.etiqueta}: ${s.valor}`).join(', ')
  return (
    <div role="img" aria-label={resumen} className={cn('flex h-1.5 w-24 overflow-hidden rounded-full bg-muted', className)}>
      {total > 0 &&
        segmentos.map((s) => (
          <span key={s.etiqueta} className={s.clase} style={{ width: `${(s.valor / total) * 100}%` }} />
        ))}
    </div>
  )
}
