import { Ban, CircleCheck, CircleDashed, CircleHelp, CircleX, LoaderCircle, type LucideIcon } from 'lucide-react'

import type { BadgeProps } from '@/components/ui/badge'

export type Estado = 'planeado' | 'corriendo' | 'paso' | 'fallo' | 'bloqueado' | 'no_concluyente'

/** Estado de un caso: texto del badge, plural de la pestaña, ícono y color. */
export const ESTADOS: Record<
  Estado,
  { texto: string; plural: string; icono: LucideIcon; variante: NonNullable<BadgeProps['variant']>; color: string }
> = {
  planeado: { texto: 'Planeado', plural: 'Planeados', icono: CircleDashed, variante: 'neutral', color: 'text-muted-foreground' },
  corriendo: { texto: 'Corriendo', plural: 'Corriendo', icono: LoaderCircle, variante: 'info', color: 'text-info' },
  paso: { texto: 'Pasó', plural: 'Pasaron', icono: CircleCheck, variante: 'success', color: 'text-success' },
  fallo: { texto: 'Falló', plural: 'Fallaron', icono: CircleX, variante: 'danger', color: 'text-danger' },
  bloqueado: { texto: 'Bloqueado', plural: 'Bloqueados', icono: Ban, variante: 'warning', color: 'text-warning' },
  no_concluyente: {
    texto: 'No concluyente',
    plural: 'No concluyentes',
    icono: CircleHelp,
    variante: 'neutral',
    color: 'text-muted-foreground',
  },
}

export const LISTA_ESTADOS = Object.keys(ESTADOS) as Estado[]
