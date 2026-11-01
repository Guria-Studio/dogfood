import { createFileRoute } from '@tanstack/react-router'

import { PageHeader } from '@/components/layout/PageHeader'

export const Route = createFileRoute('/vista')({
  component: () => (
    <>
      <PageHeader titulo="Vista en vivo" ayuda="vista" />
      <p className="text-muted-foreground">en construcción</p>
    </>
  ),
})
