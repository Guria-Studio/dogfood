import { createRootRoute, Outlet } from '@tanstack/react-router'

import { NoEncontrada } from '@/components/layout/NoEncontrada'
import { Shell } from '@/components/layout/Shell'

export const Route = createRootRoute({
  component: () => (
    <Shell>
      <Outlet />
    </Shell>
  ),
  notFoundComponent: NoEncontrada,
})
