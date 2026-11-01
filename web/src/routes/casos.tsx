import { createFileRoute } from '@tanstack/react-router'

import { PantallaCasos } from '@/features/plan/PantallaCasos'

export const Route = createFileRoute('/casos')({ component: PantallaCasos })
