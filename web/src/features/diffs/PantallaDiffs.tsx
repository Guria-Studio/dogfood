import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from '@tanstack/react-router'
import { GitCompareArrows } from 'lucide-react'
import { useState } from 'react'

import { EncabezadoPagina } from '@/components/layout/EncabezadoPagina'
import { Vacio } from '@/components/layout/Vacio'
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
import { Skeleton } from '@/components/ui/skeleton'
import { toast } from '@/components/ui/sonner'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { hace } from '@/features/casos/api'
import { lanzarDiff, useDiffs } from './api'

/** «Nuevo diff»: base `master` y, de nueva, la última comparada (o el último PR si se pega). */
function NuevoDiff({ proyecto, nuevaInicial }: { proyecto: string; nuevaInicial: string }) {
  const navigate = useNavigate()
  const cliente = useQueryClient()
  const [abierto, setAbierto] = useState(false)
  const [base, setBase] = useState('master')
  const [nueva, setNueva] = useState(nuevaInicial)
  const lanzar = useMutation({
    mutationFn: () => lanzarDiff(proyecto, { base, nueva }),
    onSuccess: (d) => {
      setAbierto(false)
      cliente.invalidateQueries({ queryKey: ['diffs', proyecto] })
      toast.success(`Diff lanzado (${d.id}); aparece en la lista al terminar.`)
      navigate({ to: '/lanzamientos/$id', params: { id: d.id } })
    },
    onError: (e) => toast.error(`No se pudo lanzar el diff: ${e.message}`),
  })
  return (
    <Dialog open={abierto} onOpenChange={setAbierto}>
      <DialogTrigger asChild>
        <Button>
          <GitCompareArrows aria-hidden="true" /> Nuevo diff
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Nuevo diff</DialogTitle>
          <DialogDescription>
            Graba los casos que ya pasaron en dos versiones y compara su comportamiento.
          </DialogDescription>
        </DialogHeader>
        <div className="grid grid-cols-2 gap-3 text-sm">
          <label className="space-y-1">
            <span>Base</span>
            <Input value={base} onChange={(e) => setBase(e.target.value)} />
          </label>
          <label className="space-y-1">
            <span>Nueva</span>
            <Input value={nueva} onChange={(e) => setNueva(e.target.value)} placeholder="rama, PR o commit" />
          </label>
        </div>
        <DialogFooter>
          <DialogClose asChild>
            <Button variant="outline">Cancelar</Button>
          </DialogClose>
          <Button onClick={() => lanzar.mutate()} disabled={lanzar.isPending || !base || !nueva}>
            {lanzar.isPending ? 'Lanzando…' : 'Lanzar'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

export function PantallaDiffs() {
  const { proyecto } = useParams({ strict: false }) as { proyecto: string }
  const { data, isPending } = useDiffs(proyecto)
  return (
    <>
      <EncabezadoPagina
        titulo="Cambios entre versiones"
        subtitulo="Qué cambió en el comportamiento de la app entre dos versiones."
        acciones={<NuevoDiff proyecto={proyecto} nuevaInicial={data?.[0]?.nueva ?? ''} />}
      />
      {isPending ? (
        <Skeleton className="h-40 w-full" />
      ) : !data?.length ? (
        <Vacio ilustracion="lista" titulo="Todavía no hay diffs" texto="Lanza uno con «Nuevo diff»." />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Versiones</TableHead>
              <TableHead>Casos con cambios</TableHead>
              <TableHead>Fecha</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((d) => (
              <TableRow key={d.id}>
                <TableCell>
                  <Link
                    to="/proyectos/$proyecto/diffs/$id"
                    params={{ proyecto, id: d.id }}
                    className="font-medium underline-offset-4 hover:underline"
                  >
                    {d.base} → {d.nueva}
                  </Link>
                </TableCell>
                <TableCell className="tabular-nums">
                  {d.con_cambios} de {d.total}
                </TableCell>
                <TableCell className="text-muted-foreground">{hace(d.creado)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </>
  )
}
