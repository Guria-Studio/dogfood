import { createFileRoute } from '@tanstack/react-router'

import { PaginaPendiente } from '@/components/layout/PaginaPendiente'

export const Route = createFileRoute('/suites')({
  component: () => (
    <PaginaPendiente
      titulo="Suites"
      subtitulo="Grupos de casos de varios proyectos que se corren juntos."
      ilustracion="lista"
      vacio="Todavía no hay suites"
      texto="Una suite junta casos de prueba para correrlos de una vez."
    />
  ),
})
