import { createFileRoute } from '@tanstack/react-router'

import { PageHeader } from '@/components/layout/PageHeader'

export const Route = createFileRoute('/ayuda/')({
  validateSearch: (s: Record<string, unknown>): { pantalla?: string } =>
    typeof s.pantalla === 'string' ? { pantalla: s.pantalla } : {},
  component: () => (
    <>
      <PageHeader titulo="Ayuda" />
      <p className="text-muted-foreground">en construcción</p>
    </>
  ),
})
