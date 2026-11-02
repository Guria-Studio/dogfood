import { createFileRoute, redirect } from '@tanstack/react-router'

import { PROYECTO_POR_DEFECTO } from '@/components/layout/pantallas'

/** Ruta vieja: ahora vive dentro del proyecto. */
export const Route = createFileRoute('/casos')({
  beforeLoad: () => {
    throw redirect({ to: '/proyectos/$proyecto/casos', params: { proyecto: PROYECTO_POR_DEFECTO }, replace: true })
  },
})
