import { createFileRoute } from '@tanstack/react-router'

import { DetalleEjecucion } from '@/features/ejecucion/DetalleEjecucion'

export const Route = createFileRoute('/ejecuciones/$id')({ component: Pantalla })

function Pantalla() {
  return <DetalleEjecucion id={Route.useParams().id} />
}
