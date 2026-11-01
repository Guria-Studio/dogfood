import { createFileRoute } from '@tanstack/react-router'

import { PageHeader } from '@/components/layout/PageHeader'

export const Route = createFileRoute('/recorridos')({
  component: () => (
    <>
      <PageHeader titulo="Recorridos" ayuda="recorridos" />
      <p className="text-muted-foreground">en construcción</p>
    </>
  ),
})
