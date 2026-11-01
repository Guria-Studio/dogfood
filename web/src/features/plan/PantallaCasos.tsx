import { Navigate } from '@tanstack/react-router'
import { ClipboardList } from 'lucide-react'

import { PageHeader } from '@/components/layout/PageHeader'
import { Vacio } from '@/components/layout/Vacio'
import { Skeleton } from '@/components/ui/skeleton'
import { useEjecuciones } from '@/features/corridas/kpis'

/** Enlace de la navegación: abre los casos de prueba de la corrida más reciente. */
export function PantallaCasos() {
  const ejecuciones = useEjecuciones()
  const ultima = ejecuciones.data?.[0]?.corrida_id
  if (ultima) return <Navigate to="/corridas/$id" params={{ id: ultima }} search={{ pestana: 'casos' }} replace />
  return (
    <>
      <PageHeader titulo="Casos de prueba" ayuda="corrida" />
      {ejecuciones.isPending ? (
        <Skeleton className="h-40 w-full" />
      ) : (
        <Vacio icono={ClipboardList} titulo="Todavía no hay corridas" texto="Corre `dogfood run` para armar el primer plan." />
      )}
    </>
  )
}
