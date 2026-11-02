import { createFileRoute } from '@tanstack/react-router'

import { DetalleCaso } from '@/features/casos/DetalleCaso'

/** Un caso a pantalla completa (el «Expandir» del sheet). */
export const Route = createFileRoute('/proyectos/$proyecto/casos/$tc')({
  component: function Pagina() {
    const { proyecto, tc } = Route.useParams()
    return (
      <div className="overflow-hidden rounded-lg border bg-card">
        <DetalleCaso proyecto={proyecto} tc={tc} />
      </div>
    )
  },
})
