import { createFileRoute } from '@tanstack/react-router'

import { PantallaCorrida } from '@/features/corridas/PantallaCorrida'

export const Route = createFileRoute('/corridas/$id')({
  component: function Corrida() {
    return <PantallaCorrida id={Route.useParams().id} />
  },
})
