import { createFileRoute } from '@tanstack/react-router'

import { PaginaPendiente } from '@/components/layout/PaginaPendiente'

export const Route = createFileRoute('/proyectos/$proyecto/actividad')({
  component: () => (
    <PaginaPendiente
      titulo="Registro"
      subtitulo="Lo que pasó en el proyecto: corridas, cambios de ajustes y casos nuevos."
      ilustracion="lista"
      vacio="Todavía no hay actividad"
      texto="Cada corrida y cada cambio del proyecto queda anotado aquí."
    />
  ),
})
