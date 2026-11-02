import { createFileRoute } from '@tanstack/react-router'

import { EncabezadoPagina } from '@/components/layout/EncabezadoPagina'
import { Documento } from '@/features/ayuda/Documento'

export const Route = createFileRoute('/ayuda/$slug')({
  component: function Pagina() {
    const { slug } = Route.useParams()
    return (
      <>
        <EncabezadoPagina titulo="Ayuda" />
        <Documento slug={slug} />
      </>
    )
  },
})
