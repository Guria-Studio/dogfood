import { Play, Plus, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { EncabezadoPagina } from '@/components/layout/EncabezadoPagina'
import { Vacio } from '@/components/layout/Vacio'
import { Badge, type BadgeProps } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

import { type EstadoSuite, escribir, useCasosElegibles, useRefrescar, useSuites } from './api'

export const ESTADOS_SUITE: Record<EstadoSuite, { texto: string; variante: NonNullable<BadgeProps['variant']> }> = {
  paso: { texto: 'Pasó', variante: 'success' },
  advertencia: { texto: 'Advertencia', variante: 'warning' },
  fallo: { texto: 'Falló', variante: 'danger' },
  bloqueado: { texto: 'Bloqueado', variante: 'warning' },
  corriendo: { texto: 'En curso', variante: 'info' },
}

function NuevaSuite({ cerrar }: { cerrar: () => void }) {
  const { data: casos = [] } = useCasosElegibles()
  const refrescar = useRefrescar()
  const [nombre, setNombre] = useState('')
  const [elegidos, setElegidos] = useState<Set<string>>(new Set())
  const clave = (c: { proyecto: string; caso: string }) => `${c.proyecto}/${c.caso}`
  const alternar = (k: string) =>
    setElegidos((s) => {
      const n = new Set(s)
      if (!n.delete(k)) n.add(k)
      return n
    })
  async function crear() {
    try {
      await escribir('/api/suites', 'POST', { nombre, casos: casos.filter((c) => elegidos.has(clave(c))).map(({ proyecto, caso }) => ({ proyecto, caso })) })
      await refrescar()
      toast.success('Suite creada')
      cerrar()
    } catch (e) {
      toast.error((e as Error).message)
    }
  }
  const proyectos = [...new Set(casos.map((c) => c.proyecto))]
  return (
    <Card className="mb-6">
      <CardContent className="space-y-4 p-6">
        <label className="block space-y-1.5 text-sm font-medium">
          Nombre de la suite
          <input className="flex w-full rounded-md border border-input bg-card px-3 py-2 text-sm" value={nombre} onChange={(e) => setNombre(e.target.value)} />
        </label>
        <fieldset className="space-y-3">
          <legend className="text-sm font-medium">Casos</legend>
          {proyectos.map((p) => (
            <div key={p}>
              <p className="text-sm font-medium text-muted-foreground">{p}</p>
              {casos.filter((c) => c.proyecto === p).map((c) => (
                <label key={clave(c)} className="flex items-center gap-2 py-1 text-sm">
                  <input type="checkbox" checked={elegidos.has(clave(c))} onChange={() => alternar(clave(c))} />
                  {c.nombre}
                </label>
              ))}
            </div>
          ))}
          {casos.length === 0 && <p className="text-sm text-muted-foreground">Todavía no hay casos en ningún proyecto.</p>}
        </fieldset>
        <div className="flex gap-2">
          <Button disabled={!nombre.trim() || elegidos.size === 0} onClick={crear}>Crear suite</Button>
          <Button variant="outline" onClick={cerrar}>Cancelar</Button>
        </div>
      </CardContent>
    </Card>
  )
}

export function Suites() {
  const { data: suites = [], isLoading } = useSuites()
  const refrescar = useRefrescar()
  const [nueva, setNueva] = useState(false)
  async function accion(f: () => Promise<unknown>, ok: string) {
    try {
      await f()
      toast.success(ok)
      await refrescar()
    } catch (e) {
      toast.error((e as Error).message)
    }
  }
  return (
    <>
      <EncabezadoPagina
        titulo="Suites"
        subtitulo="Colecciones de casos de uno o varios proyectos: humo, regresión, previa a release."
        acciones={<Button onClick={() => setNueva(true)}><Plus aria-hidden="true" /> Nueva suite</Button>}
      />
      {nueva && <NuevaSuite cerrar={() => setNueva(false)} />}
      {!isLoading && suites.length === 0 ? (
        <Vacio ilustracion="lista" titulo="Todavía no hay suites" texto="Una suite junta casos de prueba para correrlos de una vez." />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Nombre</TableHead>
              <TableHead>Última ejecución</TableHead>
              <TableHead>Casos</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead><span className="sr-only">Acciones</span></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {suites.map((s) => {
              const e = s.estado ? ESTADOS_SUITE[s.estado] : null
              return (
                <TableRow key={s.id}>
                  <TableCell className="font-medium">{s.nombre}</TableCell>
                  <TableCell>{s.ultima_ejecucion ? new Date(s.ultima_ejecucion).toLocaleString() : 'Nunca'}</TableCell>
                  <TableCell>{s.n_casos}</TableCell>
                  <TableCell>{e ? <Badge variant={e.variante}>{e.texto}</Badge> : '—'}</TableCell>
                  <TableCell className="flex justify-end gap-2">
                    <Button size="sm" onClick={() => accion(() => escribir(`/api/suites/${s.id}/correr`, 'POST'), 'Suite lanzada')}>
                      <Play aria-hidden="true" /> Correr suite
                    </Button>
                    <Button size="icon" variant="ghost" aria-label={`Borrar ${s.nombre}`} onClick={() => accion(() => escribir(`/api/suites/${s.id}`, 'DELETE'), 'Suite borrada')}>
                      <Trash2 aria-hidden="true" />
                    </Button>
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      )}
    </>
  )
}
