import { useQuery } from '@tanstack/react-query'
import { Link, useLocation } from '@tanstack/react-router'
import { ArrowLeft } from 'lucide-react'

import { cliente } from '@/api/cliente'
import { Badge } from '@/components/ui/badge'
import { calcularKpis, useEjecuciones } from '@/features/corridas/kpis'
import { cn } from '@/lib/utils'
import { GRUPOS_PROYECTO, PROYECTOS } from './pantallas'

/** Conteos de la barra: corridas y casos de la última corrida (comparte caché con la tabla de casos). */
function useConteos() {
  const ejecuciones = useEjecuciones()
  const kpis = ejecuciones.data ? calcularKpis(ejecuciones.data) : undefined
  const ultima = kpis?.ultimaCorrida
  const plan = useQuery({
    queryKey: ['plan', ultima],
    enabled: !!ultima,
    queryFn: async () => {
      const { data, error } = await cliente.GET('/api/corridas/{corrida_id}/plan', { params: { path: { corrida_id: ultima! } } })
      if (!data) throw new Error(String(error))
      return data
    },
  })
  return { corridas: kpis?.corridas, casos: plan.data?.length }
}

/** Segunda barra, dentro de un proyecto: «← Volver», el tipo y las secciones por grupo. */
export function BarraProyecto({ proyecto }: { proyecto: string }) {
  const ruta = useLocation({ select: (l) => l.pathname })
  const conteos = useConteos()
  const tipo = PROYECTOS.find((p) => p.id === proyecto)?.tipo
  const base = `/proyectos/${encodeURIComponent(proyecto)}`
  return (
    <aside
      aria-label="Barra del proyecto"
      className="border-b bg-sidebar print:hidden md:sticky md:top-14 md:h-[calc(100svh-3.5rem)] md:w-56 md:shrink-0 md:overflow-y-auto md:border-r md:border-b-0"
    >
      <div className="flex items-center gap-2 px-3 pt-3">
        <Link
          to="/proyectos"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft aria-hidden="true" className="size-4" />
          Volver
        </Link>
      </div>
      <div className="flex items-center gap-2 px-3 pt-2 pb-1">
        <span className="truncate font-semibold">{proyecto}</span>
        {tipo && <Badge variant="neutral">{tipo}</Badge>}
      </div>
      <nav aria-label="Proyecto" className="flex gap-1 overflow-x-auto p-2 md:block md:space-y-3">
        {GRUPOS_PROYECTO.map((g) => (
          <div key={g.titulo} className="flex gap-1 md:block md:space-y-0.5">
            <p className="hidden px-2 pb-1 text-xs font-medium text-muted-foreground md:block">{g.titulo}</p>
            {g.secciones.map(({ seg, texto, icono: Icono, conteo }) => {
              const to = `${base}/${seg}`
              const actual = ruta === to || ruta.startsWith(`${to}/`) || (seg === 'corridas' && ruta.startsWith(`${base}/ejecuciones`))
              const n = conteo && conteos[conteo]
              return (
                <Link
                  key={seg}
                  to={to}
                  aria-current={actual ? 'page' : undefined}
                  className={cn(
                    'flex shrink-0 items-center gap-2 rounded-md px-2 py-1.5 text-sm whitespace-nowrap hover:bg-sidebar-accent',
                    actual && 'bg-sidebar-accent font-medium',
                  )}
                >
                  <Icono aria-hidden="true" className="size-4 text-muted-foreground" />
                  <span className="flex-1">{texto}</span>
                  {n != null && <span className="text-xs tabular-nums text-muted-foreground">{n}</span>}
                </Link>
              )
            })}
          </div>
        ))}
      </nav>
    </aside>
  )
}
