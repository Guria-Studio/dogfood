import { Badge } from '@/components/ui/badge'
import { cn } from '@/lib/utils'

const COLORES: Record<string, string> = {
  aprobado: 'bg-green-600 text-white',
  rendido: 'bg-amber-500 text-black',
  fallo: 'bg-red-600 text-white',
  no_concluyente: 'bg-gray-500 text-white',
}

export const RESULTADOS = ['aprobado', 'rendido', 'fallo', 'no_concluyente']

export function BadgeResultado({ resultado, etiqueta }: { resultado: string; etiqueta?: string }) {
  return (
    <Badge data-resultado={resultado} className={cn('border-transparent', COLORES[resultado])}>
      {etiqueta ?? resultado}
    </Badge>
  )
}

export const usd = (n: number) => `$${n.toFixed(2)}`

export function duracion(s: number) {
  const m = Math.floor(s / 60)
  return m ? `${m} min ${Math.round(s % 60)} s` : `${s.toFixed(1)} s`
}

export const fecha = (iso: string) => iso.slice(0, 16).replace('T', ' ')
