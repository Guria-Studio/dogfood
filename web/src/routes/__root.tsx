import { createRootRoute, Outlet } from '@tanstack/react-router'

import { Shell } from '@/components/layout/Shell'

export const Route = createRootRoute({
  component: () => (
    <Shell>
      <Outlet />
    </Shell>
  ),
})
