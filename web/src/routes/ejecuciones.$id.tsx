import { createFileRoute, redirect } from '@tanstack/react-router'

import { PROYECTO_POR_DEFECTO } from '@/components/layout/pantallas'

/** Ruta vieja: ahora vive dentro del proyecto. */
export const Route = createFileRoute('/ejecuciones/$id')({
  beforeLoad: ({ params }) => {
    throw redirect({
      to: '/proyectos/$proyecto/ejecuciones/$id',
      params: { proyecto: PROYECTO_POR_DEFECTO, id: params.id },
      replace: true,
    })
  },
})
