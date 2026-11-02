import { createFileRoute } from '@tanstack/react-router'

import { DetalleEjecucion } from '@/features/ejecucion/DetalleEjecucion'

export const Route = createFileRoute('/proyectos/$proyecto/ejecuciones/$id')({
  component: function Ejecucion() {
    return <DetalleEjecucion id={Route.useParams().id} />
  },
})
