import { createFileRoute } from '@tanstack/react-router'

import { Fuentes } from '@/features/ajustes/Otras'

export const Route = createFileRoute('/proyectos/$proyecto/fuentes')({
  component: function Pagina() { return <Fuentes slug={Route.useParams().proyecto} /> },
})
