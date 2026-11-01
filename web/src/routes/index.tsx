import { createFileRoute } from '@tanstack/react-router'

import { PageHeader } from '@/components/layout/PageHeader'

export const Route = createFileRoute('/')({
  component: () => (
    <>
      <PageHeader titulo="Corridas" ayuda="corridas" />
      <p className="text-muted-foreground">en construcción</p>
    </>
  ),
})
