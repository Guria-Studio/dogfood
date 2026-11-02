import { createFileRoute } from '@tanstack/react-router'

import { PantallaDiffs } from '@/features/diffs/PantallaDiffs'

export const Route = createFileRoute('/proyectos/$proyecto/diffs/')({
  component: PantallaDiffs,
})
