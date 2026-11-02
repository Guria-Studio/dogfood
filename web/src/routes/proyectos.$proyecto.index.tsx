import { createFileRoute, redirect } from '@tanstack/react-router'

export const Route = createFileRoute('/proyectos/$proyecto/')({
  beforeLoad: ({ params }) => {
    throw redirect({ to: '/proyectos/$proyecto/casos', params, replace: true })
  },
})
