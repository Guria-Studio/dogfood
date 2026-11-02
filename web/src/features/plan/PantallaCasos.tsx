import { EncabezadoPagina } from '@/components/layout/EncabezadoPagina'
import { Vacio } from '@/components/layout/Vacio'
import { Skeleton } from '@/components/ui/skeleton'
import { calcularKpis, useEjecuciones } from '@/features/corridas/kpis'
import { TablaCasos } from './TablaCasos'

/** Casos de prueba del proyecto: los de la corrida más reciente. */
export function PantallaCasos() {
  const ejecuciones = useEjecuciones()
  const ultima = ejecuciones.data && calcularKpis(ejecuciones.data).ultimaCorrida
  return (
    <>
      <EncabezadoPagina
        titulo="Casos de prueba"
        subtitulo="Todos los casos de este proyecto, con su último resultado."
        ayuda="corrida"
      />
      {ultima ? (
        <TablaCasos corridaId={ultima} />
      ) : ejecuciones.isPending ? (
        <Skeleton className="h-40 w-full" />
      ) : (
        <Vacio ilustracion="lista" titulo="Todavía no hay casos de prueba" texto="Corre `dogfood run` para armar el primer plan." />
      )}
    </>
  )
}
