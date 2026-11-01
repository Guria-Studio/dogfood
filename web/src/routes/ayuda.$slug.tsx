import { createFileRoute } from '@tanstack/react-router'

import { PageHeader } from '@/components/layout/PageHeader'

export const Route = createFileRoute('/ayuda/$slug')({
  component: () => (
    <>
      <PageHeader titulo="Ayuda" />
      <p className="text-muted-foreground">en construcción</p>
    </>
  ),
})
