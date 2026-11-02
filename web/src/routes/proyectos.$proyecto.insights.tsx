import { createFileRoute } from '@tanstack/react-router'

import { PantallaInsights, validarBusquedaInsights } from '@/features/insights/PantallaInsights'

export const Route = createFileRoute('/proyectos/$proyecto/insights')({
  validateSearch: validarBusquedaInsights,
  component: PantallaInsights,
})
