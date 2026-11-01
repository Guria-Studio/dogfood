import { createFileRoute } from '@tanstack/react-router'

import { PageHeader } from '@/components/layout/PageHeader'

export const Route = createFileRoute('/ejecuciones/$id')({
  component: () => (
    <>
      <PageHeader titulo="Ejecución" ayuda="ejecucion" />
      <p className="text-muted-foreground">en construcción</p>
    </>
  ),
})
