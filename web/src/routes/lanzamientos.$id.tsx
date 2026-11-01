import { createFileRoute } from '@tanstack/react-router'

import { Progreso } from '@/features/acciones/Progreso'

export const Route = createFileRoute('/lanzamientos/$id')({
  component: function Lanzamiento() {
    return <Progreso id={Route.useParams().id} />
  },
})
