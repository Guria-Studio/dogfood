import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'

import { PageHeader } from '@/components/layout/PageHeader'
import { Button } from '@/components/ui/button'
import { toast } from '@/components/ui/sonner'
import { cancelar, estado } from './api'

/** Progreso en vivo de una corrida lanzada desde el panel (sondea cada 2 s mientras está activa). */
export function Progreso({ id }: { id: string }) {
  const qc = useQueryClient()
  const q = useQuery({
    queryKey: ['lanzamiento', id],
    queryFn: () => estado(id),
    refetchInterval: (c) => (c.state.data?.estado === 'activa' || !c.state.data ? 2000 : false),
  })
  const parar = useMutation({
    mutationFn: () => cancelar(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['lanzamiento', id] }),
    onError: (e) => toast.error(`No se pudo cancelar: ${e.message}`),
  })
  const e = q.data
  const pct = e && e.total ? Math.round((e.terminados / e.total) * 100) : 0

  return (
    <>
      <PageHeader
        titulo={`Corrida lanzada ${id}`}
        acciones={
          e?.estado === 'activa' && (
            <Button variant="destructive" onClick={() => parar.mutate()} disabled={parar.isPending}>
              Cancelar
            </Button>
          )
        }
      />
      {q.isError && <p role="alert">No se pudo leer el estado.</p>}
      {e && (
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">Estado: {e.estado}</p>
          <div>
            <div
              role="progressbar"
              aria-valuenow={pct}
              aria-valuemin={0}
              aria-valuemax={100}
              className="h-3 w-full overflow-hidden rounded-full bg-muted"
            >
              <div className="h-full bg-primary transition-all" style={{ width: `${pct}%` }} />
            </div>
            <p className="mt-1 text-sm">
              {e.terminados} de {e.total} casos terminados
            </p>
          </div>
          {e.en_curso.length > 0 && (
            <ul className="list-disc pl-5 text-sm">
              {e.en_curso.map((c) => (
                <li key={c}>En curso: {c}</li>
              ))}
            </ul>
          )}
          <p className="flex gap-4 text-sm underline">
            <Link to="/vista">Vista en vivo</Link>
            {e.corrida_id && (
              <Link to="/corridas/$id" params={{ id: e.corrida_id }}>
                Ver la corrida
              </Link>
            )}
          </p>
          <pre className="max-h-64 overflow-auto rounded-md bg-muted p-3 text-xs">{e.log.join('\n')}</pre>
        </div>
      )}
    </>
  )
}
