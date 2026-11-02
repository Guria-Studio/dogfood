import { createFileRoute, Link } from '@tanstack/react-router'
import { FolderKanban } from 'lucide-react'

import { EncabezadoPagina } from '@/components/layout/EncabezadoPagina'
import { PROYECTOS } from '@/components/layout/pantallas'
import { Button } from '@/components/ui/button'
import { Kpis } from '@/features/corridas/Kpis'

export const Route = createFileRoute('/')({
  component: () => (
    <>
      <EncabezadoPagina
        titulo="Inicio"
        subtitulo="Cómo les va a tus personas en todos los proyectos."
        acciones={
          <Button asChild variant="outline">
            <Link to="/proyectos">
              <FolderKanban aria-hidden="true" />
              Ver proyectos ({PROYECTOS.length})
            </Link>
          </Button>
        }
      />
      <Kpis />
    </>
  ),
})
