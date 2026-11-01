import { createFileRoute } from '@tanstack/react-router'

import { PageHeader } from '@/components/layout/PageHeader'

export const Route = createFileRoute('/corridas/$id')({
  component: () => (
    <>
      <PageHeader titulo="Corrida" ayuda="corrida" />
      <p className="text-muted-foreground">en construcción</p>
    </>
  ),
})
