import { createFileRoute } from '@tanstack/react-router'

import { EncabezadoPagina } from '@/components/layout/EncabezadoPagina'
import { Portada } from '@/features/ayuda/Portada'

export const Route = createFileRoute('/ayuda/')({
  validateSearch: (s: Record<string, unknown>): { pantalla?: string } =>
    typeof s.pantalla === 'string' ? { pantalla: s.pantalla } : {},
  component: function Pagina() {
    const { pantalla } = Route.useSearch()
    return (
      <>
        <EncabezadoPagina titulo="Ayuda" subtitulo="Guías, referencia y cómo funciona dogfood." />
        <Portada pantalla={pantalla} />
      </>
    )
  },
})
