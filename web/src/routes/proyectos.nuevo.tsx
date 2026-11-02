import { createFileRoute } from '@tanstack/react-router'

import { NuevoProyecto } from '@/features/proyectos/NuevoProyecto'

export const Route = createFileRoute('/proyectos/nuevo')({ component: NuevoProyecto })
