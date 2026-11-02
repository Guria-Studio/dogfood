import { createFileRoute } from '@tanstack/react-router'

import { PantallaCorridas } from '@/features/corridas/PantallaCorridas'
import { validarFiltros } from '@/features/corridas/TablaEjecuciones'

export const Route = createFileRoute('/proyectos/$proyecto/corridas/')({
  validateSearch: validarFiltros,
  component: PantallaCorridas,
})
