import { Link } from '@tanstack/react-router'
import { CircleHelp } from 'lucide-react'
import type { ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'

/** Pantallas con ayuda en contexto (`pantallas` del frontmatter de docs/ayuda). */
export type SlugPantalla =
  | 'corridas'
  | 'corrida'
  | 'recorridos'
  | 'ejecucion'
  | 'dispositivos'
  | 'vista'

interface Props {
  titulo: string
  subtitulo?: string
  ayuda?: SlugPantalla
  acciones?: ReactNode
}

export function EncabezadoPagina({ titulo, subtitulo, ayuda, acciones }: Props) {
  return (
    <header className="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div>
        <div className="flex items-center gap-1">
          <h1 className="font-serif text-3xl md:text-4xl">{titulo}</h1>
          {ayuda && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button asChild variant="ghost" size="icon" className="size-8">
                  <Link
                    to="/ayuda"
                    search={{ pantalla: ayuda }}
                    aria-label="Ayuda de esta pantalla"
                  >
                    <CircleHelp aria-hidden="true" />
                  </Link>
                </Button>
              </TooltipTrigger>
              <TooltipContent>Ayuda de esta pantalla</TooltipContent>
            </Tooltip>
          )}
        </div>
        {subtitulo && <p className="mt-1.5 text-sm text-muted-foreground">{subtitulo}</p>}
      </div>
      {acciones && <div className="flex items-center gap-2">{acciones}</div>}
    </header>
  )
}
