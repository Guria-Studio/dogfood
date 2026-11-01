import { useQuery } from '@tanstack/react-query'

import { cliente } from '@/api/cliente'
import type { components } from '@/api/schema'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

type Hallazgo = components['schemas']['HallazgoVista']

const CONFIANZA = { alta: 'success', media: 'warning', baja: 'neutral' } as const

function Tarjeta({ h }: { h: Hallazgo }) {
  const s = h.sugerencia
  if (!s) return null
  return (
    <Card data-sugerencia={h.id}>
      <CardHeader>
        <CardTitle>
          Posible causa y arreglo <Badge variant={CONFIANZA[s.confianza]}>confianza {s.confianza}</Badge>
        </CardTitle>
        <p className="text-sm text-muted-foreground">{h.titulo} · sugerido por dogfood, revisar</p>
      </CardHeader>
      <CardContent className="space-y-3 text-sm">
        <p>
          <strong>Causa probable:</strong> {s.causa}
        </p>
        {s.archivos.length > 0 && (
          <ul className="list-disc pl-5">
            {s.archivos.map((a) => (
              <li key={`${a.ruta}:${a.linea}`}>
                <a
                  className="underline"
                  href={`https://github.com/${h.repo}/blob/${h.commit || 'HEAD'}/${a.ruta}${a.linea ? `#L${a.linea}` : ''}`}
                  target="_blank"
                  rel="noreferrer"
                >
                  {a.ruta}
                  {a.linea ? `:${a.linea}` : ''}
                </a>
              </li>
            ))}
          </ul>
        )}
        <p>
          <strong>Cambio propuesto:</strong> {s.cambio}
        </p>
      </CardContent>
    </Card>
  )
}

/** Tarjetas «Posible causa y arreglo» de los hallazgos de una ejecución (nada si no hay). */
export function TarjetaSugerencia({ ejecucionId }: { ejecucionId: string }) {
  const q = useQuery({
    queryKey: ['hallazgos', ejecucionId],
    queryFn: async () => {
      const { data, error } = await cliente.GET('/api/ejecuciones/{ejecucion_id}/hallazgos', {
        params: { path: { ejecucion_id: ejecucionId } },
      })
      if (!data) throw new Error(JSON.stringify(error))
      return data
    },
  })
  return (
    <>
      {(q.data ?? []).map((h) => (
        <Tarjeta key={h.id} h={h} />
      ))}
    </>
  )
}
