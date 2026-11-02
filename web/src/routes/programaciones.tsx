import { createFileRoute } from '@tanstack/react-router'

import { Programaciones } from '@/features/suites/Programaciones'

export const Route = createFileRoute('/programaciones')({ component: Programaciones })
