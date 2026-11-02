import { createFileRoute, notFound } from '@tanstack/react-router'

import { Comportamiento, EntornoPagina, General, Notificaciones } from '@/features/ajustes/Paginas'

const SECCIONES = { general: General, entorno: EntornoPagina, comportamiento: Comportamiento, notificaciones: Notificaciones }

export const Route = createFileRoute('/proyectos/$proyecto/ajustes/$seccion')({
  beforeLoad: ({ params }) => {
    if (!(params.seccion in SECCIONES)) throw notFound()
  },
  component: function Ajustes() {
    const { proyecto, seccion } = Route.useParams()
    const Pagina = SECCIONES[seccion as keyof typeof SECCIONES]
    return <Pagina key={`${proyecto}/${seccion}`} slug={proyecto} />
  },
})
