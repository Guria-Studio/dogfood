import { createFileRoute } from '@tanstack/react-router'

import { PaginaPendiente } from '@/components/layout/PaginaPendiente'

export const Route = createFileRoute('/programaciones')({
  component: () => (
    <PaginaPendiente
      titulo="Programaciones"
      subtitulo="Corridas que se lanzan solas a una hora fija."
      ilustracion="calendario"
      vacio="Todavía no hay programaciones"
      texto="Programa una corrida para que dogfood revise tu app cada día o cada semana."
    />
  ),
})
