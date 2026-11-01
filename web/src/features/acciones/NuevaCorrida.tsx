import { useMutation, useQuery } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { Play } from 'lucide-react'
import { useState } from 'react'

import { cliente } from '@/api/cliente'
import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { toast } from '@/components/ui/sonner'
import { lanzarCorrida } from './api'

/** Botón «Nueva corrida» con su formulario; al lanzar, abre la página de progreso. */
export function NuevaCorrida() {
  const navigate = useNavigate()
  const [abierto, setAbierto] = useState(false)
  const [objetivo, setObjetivo] = useState('predicts')
  const [ref, setRef] = useState('main')
  const [personas, setPersonas] = useState(3)
  const [escenarios, setEscenarios] = useState<string[]>([])
  const [publicar, setPublicar] = useState(false)

  const recorridos = useQuery({
    queryKey: ['recorridos', objetivo],
    queryFn: async () =>
      (await cliente.GET('/api/recorridos', { params: { query: { objetivo } } })).data ?? [],
    enabled: abierto,
  })
  const lanzar = useMutation({
    mutationFn: () => lanzarCorrida({ objetivo, ref, personas, escenarios, sin_publicar: !publicar }),
    onSuccess: (d) => {
      setAbierto(false)
      navigate({ to: '/lanzamientos/$id', params: { id: d.id } })
    },
    onError: (e) => toast.error(`No se pudo lanzar la corrida: ${e.message}`),
  })

  return (
    <Dialog open={abierto} onOpenChange={setAbierto}>
      <DialogTrigger asChild>
        <Button>
          <Play aria-hidden="true" /> Nueva corrida
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nueva corrida</DialogTitle>
          <DialogDescription>Lanza usuarios agénticos contra el objetivo.</DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <label className="space-y-1">
            <span>Objetivo</span>
            <Input value={objetivo} onChange={(e) => setObjetivo(e.target.value)} />
          </label>
          <label className="space-y-1">
            <span>Ref</span>
            <Input value={ref} onChange={(e) => setRef(e.target.value)} />
          </label>
          <label className="space-y-1">
            <span>Personas</span>
            <Input
              type="number"
              min={1}
              max={50}
              value={personas}
              onChange={(e) => setPersonas(Number(e.target.value))}
            />
          </label>
          <label className="col-span-2 space-y-1">
            <span>Escenarios (ninguno = todos)</span>
            <select
              multiple
              aria-label="Escenarios"
              className="h-28 w-full rounded-md border border-input bg-background px-2 text-sm"
              value={escenarios}
              onChange={(e) => setEscenarios(Array.from(e.target.selectedOptions, (o) => o.value))}
            >
              {(recorridos.data ?? []).map((r) => (
                <option key={r.id} value={r.id}>
                  {r.titulo}
                </option>
              ))}
            </select>
          </label>
          <label className="col-span-2 flex items-center gap-2">
            <input type="checkbox" checked={publicar} onChange={(e) => setPublicar(e.target.checked)} />
            Publicar los hallazgos como issues
          </label>
          {publicar && (
            <p role="alert" className="col-span-2 rounded-md bg-destructive/10 px-3 py-2 text-destructive">
              Esto publica en GitHub: se crearán issues reales en el repositorio del objetivo.
            </p>
          )}
        </div>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline">Cancelar</Button>
          </DialogClose>
          <Button onClick={() => lanzar.mutate()} disabled={lanzar.isPending}>
            {lanzar.isPending ? 'Lanzando…' : 'Lanzar'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
