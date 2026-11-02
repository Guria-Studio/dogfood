import { createFileRoute } from '@tanstack/react-router'

import { ListaProyectos } from '@/features/proyectos/ListaProyectos'

export const Route = createFileRoute('/proyectos/')({ component: ListaProyectos })
