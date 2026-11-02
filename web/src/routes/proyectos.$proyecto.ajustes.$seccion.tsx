import { createFileRoute, notFound } from '@tanstack/react-router'

import { PaginaPendiente } from '@/components/layout/PaginaPendiente'

const SECCIONES: Record<string, [titulo: string, subtitulo: string]> = {
  general: ['General', 'Nombre, tipo y URL del proyecto.'],
  entorno: ['Entorno', 'Dónde corre la app: URL, dispositivo y credenciales de prueba.'],
  comportamiento: ['Comportamiento', 'Timeout, viewport, reintentos y motor de cada corrida.'],
  notificaciones: ['Notificaciones', 'A quién avisar cuando una corrida termina o falla.'],
}

export const Route = createFileRoute('/proyectos/$proyecto/ajustes/$seccion')({
  beforeLoad: ({ params }) => {
    if (!SECCIONES[params.seccion]) throw notFound()
  },
  component: function Ajustes() {
    const [titulo, subtitulo] = SECCIONES[Route.useParams().seccion]
    return (
      <PaginaPendiente
        titulo={titulo}
        subtitulo={subtitulo}
        ilustracion="carpeta"
        vacio="Estos ajustes todavía no se pueden editar"
        texto="Hoy salen de la configuración del objetivo en el servidor."
      />
    )
  },
})
