import { createFileRoute } from '@tanstack/react-router'

import { PageHeader } from '@/components/layout/PageHeader'

export const Route = createFileRoute('/dispositivos')({
  component: () => (
    <>
      <PageHeader titulo="Dispositivos" ayuda="dispositivos" />
      <p className="text-muted-foreground">en construcción</p>
    </>
  ),
})
