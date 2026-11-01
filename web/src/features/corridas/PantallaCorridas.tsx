import { useQuery } from '@tanstack/react-query'
import { useNavigate, useSearch } from '@tanstack/react-router'

import { cliente } from '@/api/cliente'
import { PageHeader } from '@/components/layout/PageHeader'
import { FILTROS, type Filtros, TablaEjecuciones } from './TablaEjecuciones'

export function PantallaCorridas() {
  const filtros: Filtros = useSearch({ strict: false })
  const navigate = useNavigate()
  const opciones = useQuery({
    queryKey: ['filtros'],
    queryFn: async () => (await cliente.GET('/api/filtros')).data ?? {},
  })

  const cambiar = (nombre: string, valor: string) =>
    navigate({ to: '/', search: { ...filtros, [nombre]: valor || undefined } })

  return (
    <>
      <PageHeader titulo="Corridas" ayuda="corridas" />
      <div className="mb-4 flex flex-wrap gap-3">
        {FILTROS.map((nombre) => (
          <label key={nombre} className="flex flex-col gap-1 text-sm capitalize">
            {nombre}
            <select
              aria-label={nombre}
              value={filtros[nombre] ?? ''}
              onChange={(e) => cambiar(nombre, e.target.value)}
              className="h-9 rounded-md border bg-background px-2 text-sm"
            >
              <option value="">todos</option>
              {(opciones.data?.[nombre] ?? []).map((o) => (
                <option key={o.valor} value={o.valor}>
                  {o.etiqueta}
                </option>
              ))}
            </select>
          </label>
        ))}
      </div>
      <TablaEjecuciones filtros={filtros} />
    </>
  )
}
