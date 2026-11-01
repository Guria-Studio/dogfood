import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

interface Props {
  icono: LucideIcon
  titulo: string
  texto?: ReactNode
  accion?: ReactNode
  /** Para errores: lo anuncia el lector de pantalla. */
  error?: boolean
  className?: string
}

/** Estado vacío o de error común a todas las pantallas. */
export function Vacio({ icono: Icono, titulo, texto, accion, error, className }: Props) {
  return (
    <div
      role={error ? 'alert' : undefined}
      className={cn(
        'flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed px-6 py-12 text-center',
        className,
      )}
    >
      <div
        className={cn(
          'grid size-12 place-items-center rounded-full',
          error ? 'bg-danger-soft text-danger' : 'bg-accent text-accent-foreground',
        )}
      >
        <Icono aria-hidden="true" className="size-6" />
      </div>
      <div className="max-w-md space-y-1">
        <p className="font-medium">{titulo}</p>
        {texto && <div className="text-sm text-muted-foreground">{texto}</div>}
      </div>
      {accion && <div className="mt-1 flex flex-wrap justify-center gap-2">{accion}</div>}
    </div>
  )
}
