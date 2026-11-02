import { createFileRoute } from '@tanstack/react-router'

import { PantallaCasos, validarBusquedaCasos } from '@/features/casos/PantallaCasos'

export const Route = createFileRoute('/proyectos/$proyecto/casos/')({
  validateSearch: validarBusquedaCasos,
  component: PantallaCasos,
})
