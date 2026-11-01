import { useMutation } from '@tanstack/react-query'
import { RotateCcw } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { toast } from '@/components/ui/sonner'
import { repetirCaso } from './api'

/** Lanza `dogfood replay` de la ejecución. */
export function RepetirCaso({ ejecucionId }: { ejecucionId: string }) {
  const m = useMutation({
    mutationFn: () => repetirCaso(ejecucionId),
    onSuccess: (d) => toast.success(`Repetición lanzada (${d.id})`),
    onError: (e) => toast.error(`No se pudo repetir el caso: ${e.message}`),
  })
  return (
    <Button variant="outline" onClick={() => m.mutate()} disabled={m.isPending}>
      <RotateCcw aria-hidden="true" /> Repetir caso
    </Button>
  )
}
