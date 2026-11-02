import { createFileRoute, redirect } from '@tanstack/react-router'

import { PROYECTO_POR_DEFECTO } from '@/components/layout/pantallas'

/** Ruta vieja: ahora vive dentro del proyecto. El reporte (`/corridas/$id/reporte`) sigue aquí. */
export const Route = createFileRoute('/corridas/$id/')({
  validateSearch: validarPestana,
  beforeLoad: ({ params, search }) => {
    throw redirect({
      to: '/proyectos/$proyecto/corridas/$id',
      params: { proyecto: PROYECTO_POR_DEFECTO, id: params.id },
      search,
      replace: true,
    })
  },
})

function validarPestana(s: Record<string, unknown>): { pestana?: 'casos' } {
  return s.pestana === 'casos' ? { pestana: 'casos' } : {}
}
