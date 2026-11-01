import { createFileRoute } from '@tanstack/react-router'

import { PantallaRecorridos } from '@/features/corridas/PantallaRecorridos'

export const Route = createFileRoute('/recorridos')({ component: PantallaRecorridos })
