import { createFileRoute } from '@tanstack/react-router'

import { PantallaCorrida } from '@/features/corridas/PantallaCorrida'

export const Route = createFileRoute('/proyectos/$proyecto/corridas/$id')({
  validateSearch: (s: Record<string, unknown>): { pestana?: 'casos' } =>
    s.pestana === 'casos' ? { pestana: 'casos' } : {},
  component: function Corrida() {
    return <PantallaCorrida id={Route.useParams().id} />
  },
})
