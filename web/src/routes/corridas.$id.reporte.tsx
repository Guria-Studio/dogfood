import { createFileRoute } from '@tanstack/react-router'

import { PantallaReporte } from '@/features/reporte/PantallaReporte'

export const Route = createFileRoute('/corridas/$id/reporte')({
  component: function Reporte() {
    return <PantallaReporte id={Route.useParams().id} />
  },
})
