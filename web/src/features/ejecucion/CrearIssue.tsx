import { useMutation } from '@tanstack/react-query'
import { Bug } from 'lucide-react'
import { useState } from 'react'

import { cliente } from '@/api/cliente'
import type { components } from '@/api/schema'
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
import { toast } from '@/components/ui/sonner'

type Tipo = components['schemas']['TipoHallazgo']
type Gravedad = components['schemas']['Gravedad']
const TIPOS: Tipo[] = ['tecnico', 'logica', 'aislamiento', 'regla', 'friccion', 'accesibilidad']
const GRAVEDADES: Gravedad[] = ['critica', 'alta', 'media', 'baja']

/** Mensaje legible de cualquier cuerpo de error de la API (`ErrorApi`, `HTTPException` o 422). */
function mensajeError(error: unknown, status: number) {
  const e = error as { detalle?: string; detail?: unknown } | undefined
  if (e?.detalle) return e.detalle
  if (typeof e?.detail === 'string') return e.detail
  return `error ${status}`
}

const select =
  'h-9 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none'

/** Publica la ejecución como issue en GitHub, previa confirmación. */
export function CrearIssue({ ejecucionId, titulo }: { ejecucionId: string; titulo: string }) {
  const [abierto, setAbierto] = useState(false)
  const [tipo, setTipo] = useState<Tipo>('tecnico')
  const [gravedad, setGravedad] = useState<Gravedad>('media')
  const [url, setUrl] = useState<string | null>(null)

  const publicar = useMutation({
    mutationFn: async () => {
      const { data, error, response } = await cliente.POST('/api/ejecuciones/{ejecucion_id}/issue', {
        params: {
          path: { ejecucion_id: ejecucionId },
          query: { tipo, gravedad },
          header: { 'x-dogfood': '1' }, // el backend rechaza el POST sin él (CSRF)
        },
      })
      if (!data) throw new Error(mensajeError(error, response.status))
      return data
    },
    onSuccess: (d) => {
      setAbierto(false)
      if (d.url) {
        setUrl(d.url)
        toast.success(
          <span>
            Issue {d.accion}:{' '}
            <a href={d.url} target="_blank" rel="noreferrer" className="underline">
              {d.url}
            </a>
          </span>,
          { duration: 15000 },
        )
      } else toast.info(`${d.accion} ${d.aviso}`.trim())
    },
    onError: (e) => {
      setAbierto(false)
      toast.error(`No se pudo crear el issue: ${e.message}`)
    },
  })

  return (
    <div className="flex items-center gap-3">
      {url && (
        <a href={url} target="_blank" rel="noreferrer" className="text-sm underline">
          Ver issue
        </a>
      )}
      <Dialog open={abierto} onOpenChange={setAbierto}>
        <DialogTrigger asChild>
          <Button>
            <Bug aria-hidden="true" /> Crear issue
          </Button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>¿Crear el issue?</DialogTitle>
            <DialogDescription>
              Se publica en el repositorio de GitHub configurado para el objetivo. Si ya existe uno
              con la misma huella, se comenta en él.
            </DialogDescription>
          </DialogHeader>
          <p className="rounded-md bg-muted px-3 py-2 text-sm font-medium" data-testid="titulo-issue">
            {titulo}
          </p>
          <div className="grid grid-cols-2 gap-3">
            <label className="space-y-1 text-sm">
              <span>Tipo</span>
              <select className={select} value={tipo} onChange={(e) => setTipo(e.target.value as Tipo)}>
                {TIPOS.map((t) => (
                  <option key={t}>{t}</option>
                ))}
              </select>
            </label>
            <label className="space-y-1 text-sm">
              <span>Gravedad</span>
              <select
                className={select}
                value={gravedad}
                onChange={(e) => setGravedad(e.target.value as Gravedad)}
              >
                {GRAVEDADES.map((g) => (
                  <option key={g}>{g}</option>
                ))}
              </select>
            </label>
          </div>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">Cancelar</Button>
            </DialogClose>
            <Button onClick={() => publicar.mutate()} disabled={publicar.isPending}>
              {publicar.isPending ? 'Publicando…' : 'Publicar'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  )
}
