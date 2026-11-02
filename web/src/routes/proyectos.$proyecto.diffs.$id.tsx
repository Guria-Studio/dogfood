import { createFileRoute } from '@tanstack/react-router'

import { DetalleDiff } from '@/features/diffs/DetalleDiff'

export const Route = createFileRoute('/proyectos/$proyecto/diffs/$id')({
  component: DetalleDiff,
})
