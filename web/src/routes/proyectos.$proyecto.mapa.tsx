import { createFileRoute } from '@tanstack/react-router'

import { Mapa } from '@/features/mapa/Mapa'

export const Route = createFileRoute('/proyectos/$proyecto/mapa')({ component: Mapa })
