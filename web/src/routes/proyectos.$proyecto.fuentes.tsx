import { createFileRoute } from '@tanstack/react-router'

import { PaginaPendiente } from '@/components/layout/PaginaPendiente'

export const Route = createFileRoute('/proyectos/$proyecto/fuentes')({
  component: () => (
    <PaginaPendiente
      titulo="Fuentes"
      subtitulo="De dónde sale el contexto del proyecto: repositorio, documentos y URL de la app."
      ilustracion="carpeta"
      vacio="Todavía no hay fuentes"
      texto="Las fuentes del proyecto se configuran al crearlo."
    />
  ),
})
