import { createFileRoute } from '@tanstack/react-router'

import { PageHeader } from '@/components/layout/PageHeader'
import { Documento } from '@/features/ayuda/Documento'

export const Route = createFileRoute('/ayuda/$slug')({
  component: function Pagina() {
    const { slug } = Route.useParams()
    return (
      <>
        <PageHeader titulo="Ayuda" />
        <Documento slug={slug} />
      </>
    )
  },
})
