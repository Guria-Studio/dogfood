import { useQuery } from '@tanstack/react-query'
import { ListChecks, TriangleAlert } from 'lucide-react'

import { cliente } from '@/api/cliente'
import { PageHeader } from '@/components/layout/PageHeader'
import { Vacio } from '@/components/layout/Vacio'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { BadgeResultado, RESULTADOS } from './comun'
const BARRA: Record<string, string> = {
  aprobado: 'bg-green-600',
  rendido: 'bg-amber-500',
  fallo: 'bg-red-600',
  no_concluyente: 'bg-gray-500',
}

export function PantallaRecorridos() {
  const recorridos = useQuery({
    queryKey: ['recorridos'],
    queryFn: async () => {
      const { data, error } = await cliente.GET('/api/recorridos')
      if (!data) throw new Error(String(error))
      return data
    },
  })
  const etiquetas = useQuery({
    queryKey: ['etiquetas'],
    queryFn: async () => (await cliente.GET('/api/etiquetas')).data ?? {},
  })

  let cuerpo
  if (recorridos.isError)
    cuerpo = <Vacio error icono={TriangleAlert} titulo="No se pudieron cargar los recorridos" texto="Revisa que el panel esté corriendo y vuelve a intentar." />
  else if (recorridos.isPending) cuerpo = <Skeleton data-testid="cargando" className="h-40 w-full" />
  else if (recorridos.data.length === 0)
    cuerpo = <Vacio icono={ListChecks} titulo="Este objetivo no tiene escenarios" texto="Los recorridos salen de los escenarios del objetivo configurado." />
  else
    cuerpo = (
      <div className="space-y-4">
        {recorridos.data.map((r) => {
          const total = Object.values(r.por_resultado).reduce((a, b) => a + b, 0)
          return (
            <Card key={r.id}>
              <CardHeader>
                <CardTitle>
                  {r.titulo}{' '}
                  <small className="font-normal text-muted-foreground">
                    ({r.id} · {r.driver})
                  </small>
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="space-y-1">
                  {RESULTADOS.filter((k) => k in r.por_resultado).map((k) => (
                    <div key={k} className="flex items-center gap-2 text-sm">
                      <span className="w-32 shrink-0">
                        <BadgeResultado resultado={k} etiqueta={etiquetas.data?.[k]} />
                      </span>
                      <div className="h-3 flex-1 rounded bg-muted">
                        <div
                          className={`h-3 rounded ${BARRA[k]}`}
                          style={{ width: `${total ? (r.por_resultado[k] / total) * 100 : 0}%` }}
                        />
                      </div>
                      <span className="w-8 text-right">{r.por_resultado[k]}</span>
                    </div>
                  ))}
                </div>
                {r.contrato ? (
                  <dl className="space-y-1 text-sm">
                    <dt className="font-medium">Estado inicial</dt>
                    <dd>{r.contrato.estado_inicial || '—'}</dd>
                    <dt className="font-medium">Acciones</dt>
                    <dd>
                      <ol className="list-decimal pl-5">
                        {r.contrato.acciones.map((a) => (
                          <li key={a}>{a}</li>
                        ))}
                      </ol>
                    </dd>
                    <dt className="font-medium">Resultado esperado</dt>
                    <dd>{r.contrato.resultado_esperado || '—'}</dd>
                    <dt className="font-medium">Evidencia requerida</dt>
                    <dd>
                      <ul className="list-disc pl-5">
                        {r.contrato.evidencia_requerida.map((e) => (
                          <li key={e}>{e}</li>
                        ))}
                      </ul>
                    </dd>
                  </dl>
                ) : (
                  <p className="text-sm text-muted-foreground">Sin contrato definido.</p>
                )}
              </CardContent>
            </Card>
          )
        })}
      </div>
    )

  return (
    <>
      <PageHeader titulo="Recorridos" ayuda="recorridos" />
      {cuerpo}
    </>
  )
}
