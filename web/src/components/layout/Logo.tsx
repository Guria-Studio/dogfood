import logo from '@/assets/logo.svg'
import { cn } from '@/lib/utils'

/** El logo como máscara: toma el color del texto (`currentColor`) en tema claro y oscuro. */
export function Logo({ className }: { className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cn('inline-block size-6 shrink-0 bg-current', className)}
      style={{ mask: `url(${logo}) center / contain no-repeat` }}
    />
  )
}
