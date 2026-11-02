import { createFileRoute, Link } from '@tanstack/react-router'
import { ChevronRight } from 'lucide-react'

import { EncabezadoPagina } from '@/components/layout/EncabezadoPagina'
import { PROYECTOS } from '@/components/layout/pantallas'
import { Badge } from '@/components/ui/badge'

export const Route = createFileRoute('/proyectos/')({
  component: () => (
    <>
      <EncabezadoPagina titulo="Proyectos" subtitulo="Cada proyecto es una app que dogfood prueba con sus personas." />
      <ul className="divide-y rounded-xl border bg-card">
        {PROYECTOS.map((p) => (
          <li key={p.id}>
            <Link
              to="/proyectos/$proyecto/casos"
              params={{ proyecto: p.id }}
              className="flex items-center gap-3 px-4 py-3 hover:bg-muted/60"
            >
              <span className="font-medium">{p.nombre}</span>
              <Badge variant="neutral">{p.tipo}</Badge>
              <ChevronRight aria-hidden="true" className="ml-auto size-4 text-muted-foreground" />
            </Link>
          </li>
        ))}
      </ul>
    </>
  ),
})
