import { createFileRoute } from '@tanstack/react-router'

import { PaginaPendiente } from '@/components/layout/PaginaPendiente'

export const Route = createFileRoute('/proyectos/$proyecto/insights')({
  component: () => (
    <PaginaPendiente
      titulo="Insights"
      subtitulo="Qué arreglar primero: issues agrupados por causa, tendencia y cobertura por caso de uso."
      ilustracion="grafico"
      vacio="Todavía no hay insights"
      texto="Aparecen cuando el proyecto tenga corridas con resultados."
    />
  ),
})
