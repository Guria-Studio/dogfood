import { createFileRoute } from '@tanstack/react-router'

import { PaginaPendiente } from '@/components/layout/PaginaPendiente'

export const Route = createFileRoute('/proyectos/$proyecto/github')({
  component: () => (
    <PaginaPendiente
      titulo="Acción de GitHub"
      subtitulo="Corre los casos del proyecto en cada pull request."
      ilustracion="lista"
      vacio="La acción de GitHub no está instalada"
      texto="Cuando la instales, sus corridas aparecen junto a las del panel."
    />
  ),
})
