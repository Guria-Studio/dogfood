import { createFileRoute } from '@tanstack/react-router'

import { AccionGithub } from '@/features/ajustes/Otras'

export const Route = createFileRoute('/proyectos/$proyecto/github')({
  component: function Pagina() { return <AccionGithub slug={Route.useParams().proyecto} /> },
})
