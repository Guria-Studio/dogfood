import { useParams } from '@tanstack/react-router'
import { useMutation } from '@tanstack/react-query'

import { EncabezadoPagina } from '@/components/layout/EncabezadoPagina'
import { Vacio } from '@/components/layout/Vacio'
import { Button } from '@/components/ui/button'
import { generarPlan } from '@/features/proyectos/api'
import { Skeleton } from '@/components/ui/skeleton'
import { calcularKpis, useEjecuciones } from '@/features/corridas/kpis'
import { TablaCasos } from './TablaCasos'

/** Casos de prueba del proyecto: los de la corrida más reciente. */
export function PantallaCasos() {
  const ejecuciones = useEjecuciones()
  const { proyecto } = useParams({ strict: false })
  const plan = useMutation({ mutationFn: () => generarPlan(proyecto ?? '') })
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
        <Vacio
          ilustracion="lista"
          titulo="Genera el plan"
          texto={plan.error ? plan.error.message : plan.isSuccess ? 'Plan en marcha: vuelve en un momento.' : 'Todavía no hay casos de prueba: dogfood plan los arma.'}
          accion={<Button disabled={plan.isPending || !proyecto} onClick={() => plan.mutate()}>Generar plan</Button>}
        />
      )}
    </>
  )
}
