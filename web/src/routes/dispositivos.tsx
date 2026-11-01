import { createFileRoute } from '@tanstack/react-router'

import { PageHeader } from '@/components/layout/PageHeader'
import { Dispositivos } from '@/features/vivo/Dispositivos'

export const Route = createFileRoute('/dispositivos')({
  component: () => (
    <>
      <PageHeader titulo="Dispositivos" ayuda="dispositivos" />
      <Dispositivos />
    </>
  ),
})
