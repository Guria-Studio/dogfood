import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

/** Ilustraciones lineales simples (trazo `currentColor`) para los estados vacíos. */
const ILUSTRACIONES = {
  lista: (
    <>
      <rect x="18" y="10" width="44" height="58" rx="5" />
      <path d="M30 26h20M30 38h20M30 50h12" />
      <circle cx="58" cy="58" r="10" className="fill-background" />
      <path d="M54 58h8M58 54v8" />
    </>
  ),
  calendario: (
    <>
      <rect x="12" y="16" width="56" height="50" rx="5" />
      <path d="M12 30h56M26 10v12M54 10v12" />
      <path d="M24 42h6M37 42h6M50 42h6M24 54h6M37 54h6" />
    </>
  ),
  grafico: (
    <>
      <path d="M12 66h56M16 66V14" />
      <path d="M22 54l12-14 10 8 18-22" />
      <circle cx="62" cy="26" r="3" />
    </>
  ),
  carpeta: (
    <>
      <path d="M10 24a4 4 0 0 1 4-4h16l6 6h30a4 4 0 0 1 4 4v32a4 4 0 0 1-4 4H14a4 4 0 0 1-4-4z" />
      <path d="M10 34h60" />
    </>
  ),
}

export type Ilustracion = keyof typeof ILUSTRACIONES

interface Props {
  icono?: LucideIcon
  /** En lugar del ícono: dibujo lineal más grande. */
  ilustracion?: Ilustracion
  titulo: string
  texto?: ReactNode
  accion?: ReactNode
  /** Para errores: lo anuncia el lector de pantalla. */
  error?: boolean
  className?: string
}

/** Estado vacío o de error común a todas las pantallas. */
export function Vacio({ icono: Icono, ilustracion, titulo, texto, accion, error, className }: Props) {
  return (
    <div
      role={error ? 'alert' : undefined}
      className={cn(
        'flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed bg-card px-6 py-12 text-center',
        className,
      )}
    >
      {ilustracion ? (
        <svg
          viewBox="0 0 80 80"
          aria-hidden="true"
          className="size-20 fill-none stroke-muted-foreground"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          {ILUSTRACIONES[ilustracion]}
        </svg>
      ) : (
        Icono && (
          <div
            className={cn(
              'grid size-12 place-items-center rounded-full',
              error ? 'bg-danger-soft text-danger' : 'bg-accent text-accent-foreground',
            )}
          >
            <Icono aria-hidden="true" className="size-6" />
          </div>
        )
      )}
      <div className="max-w-md space-y-1">
        <p className="font-medium">{titulo}</p>
        {texto && <div className="text-sm text-muted-foreground">{texto}</div>}
      </div>
      {accion && <div className="mt-1 flex flex-wrap justify-center gap-2">{accion}</div>}
    </div>
  )
}
