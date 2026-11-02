import { createFileRoute } from '@tanstack/react-router'

import { Suites } from '@/features/suites/Suites'

export const Route = createFileRoute('/suites')({ component: Suites })
