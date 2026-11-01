import { createFileRoute } from '@tanstack/react-router'

import { PageHeader } from '@/components/layout/PageHeader'
import { VistaVivo } from '@/features/vivo/VistaVivo'

export const Route = createFileRoute('/vista')({
  component: () => (
    <>
      <PageHeader titulo="Vista en vivo" ayuda="vista" />
      <VistaVivo />
    </>
  ),
})
