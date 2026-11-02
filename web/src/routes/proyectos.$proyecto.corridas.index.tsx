import { createFileRoute } from '@tanstack/react-router'

import { ListaCorridas } from '@/features/corridas/ListaCorridas'
import { validarFiltros } from '@/features/corridas/TablaEjecuciones'

export const Route = createFileRoute('/proyectos/$proyecto/corridas/')({
  validateSearch: validarFiltros,
  component: ListaCorridas,
})
