import { createFileRoute } from '@tanstack/react-router'

import { PantallaCorrida, type Pestana } from '@/features/corridas/PantallaCorrida'

export const Route = createFileRoute('/proyectos/$proyecto/corridas/$id')({
  validateSearch: (s: Record<string, unknown>): { pestana?: Pestana } =>
    s.pestana === 'lista' || s.pestana === 'resumen' || s.pestana === 'acciones' ? { pestana: s.pestana } : {},
  component: function Corrida() {
    return <PantallaCorrida id={Route.useParams().id} />
  },
})
