import { createFileRoute, redirect } from '@tanstack/react-router'

import { PROYECTO_POR_DEFECTO } from '@/components/layout/pantallas'

/** Ruta vieja: ahora vive dentro del proyecto. */
export const Route = createFileRoute('/vista')({
  beforeLoad: () => {
    throw redirect({ to: '/proyectos/$proyecto/vista', params: { proyecto: PROYECTO_POR_DEFECTO }, replace: true })
  },
})
