import { createFileRoute } from '@tanstack/react-router'

import { Actividad } from '@/features/ajustes/Otras'

export const Route = createFileRoute('/proyectos/$proyecto/actividad')({
  component: function Pagina() { return <Actividad slug={Route.useParams().proyecto} /> },
})
