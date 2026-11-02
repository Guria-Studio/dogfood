import { useQuery } from '@tanstack/react-query'

import { cliente } from '@/api/cliente'
import type { components } from '@/api/schema'

export type Insights = components['schemas']['Insights']

export function useInsights(proyecto: string) {
  return useQuery({
    queryKey: ['insights', proyecto],
    queryFn: async () => {
      const { data, error } = await cliente.GET('/api/proyectos/{slug}/insights', {
        params: { path: { slug: proyecto } },
      })
      if (!data) throw new Error(JSON.stringify(error))
      return data
    },
  })
}
