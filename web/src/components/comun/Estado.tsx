import { useNavigate, useSearch } from '@tanstack/react-router'
import { List } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'
import { ESTADOS, type Estado, LISTA_ESTADOS } from './estados'

export function BadgeEstado({ estado, className }: { estado: Estado; className?: string }) {
  const e = ESTADOS[estado]
  const Icono = e.icono
  return (
    <Badge data-estado={estado} variant={e.variante} className={className}>
      <Icono aria-hidden="true" />
      {e.texto}
    </Badge>
  )
}

/** Pestañas «Todos 19 · Pasaron 2 · Fallaron 17…»: el filtro vive en la URL (`?estado=fallo`). */
export function PestanasEstado({
  conteos,
  estados = LISTA_ESTADOS,
}: {
  conteos: Partial<Record<Estado, number>>
  estados?: Estado[]
}) {
  const navigate = useNavigate()
  const { estado } = useSearch({ strict: false }) as { estado?: string }
  const total = estados.reduce((n, e) => n + (conteos[e] ?? 0), 0)
  const pestanas = [
    { id: 'todos', texto: 'Todos', icono: List, color: 'text-foreground', n: total },
    ...estados.map((e) => ({ id: e, texto: ESTADOS[e].plural, icono: ESTADOS[e].icono, color: ESTADOS[e].color, n: conteos[e] ?? 0 })),
  ]
  return (
    <Tabs
      value={estado ?? 'todos'}
      onValueChange={(v) =>
        navigate({
          to: '.',
          search: ((s: Record<string, unknown>) => ({ ...s, estado: v === 'todos' ? undefined : v })) as never,
        })
      }
    >
      <TabsList aria-label="Filtrar por estado">
        {pestanas.map(({ id, texto, icono: Icono, color, n }) => (
          <TabsTrigger key={id} value={id} className="gap-1.5">
            <Icono aria-hidden="true" className={cn('size-4', color)} />
            {texto}
            <span className="rounded bg-muted px-1.5 text-xs tabular-nums text-muted-foreground">{n}</span>
          </TabsTrigger>
        ))}
      </TabsList>
    </Tabs>
  )
}
