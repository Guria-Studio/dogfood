import { Moon, Plus, Repeat, Trash2, TrendingUp } from 'lucide-react'
import { useState } from 'react'
import { toast } from 'sonner'

import { EncabezadoPagina } from '@/components/layout/EncabezadoPagina'
import { Vacio } from '@/components/layout/Vacio'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'

import { escribir, type Programacion, useProgramaciones, useRefrescar, useSuites } from './api'

const FRECUENCIAS = { hora: 'Cada hora', dia: 'A diario', semana: 'Cada semana', cron: 'Expresión cron' } as const
const DIAS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const campo = 'flex w-full rounded-md border border-input bg-card px-3 py-2 text-sm'

const BENEFICIOS = [
  { icono: Repeat, titulo: 'Corridas sin pedirlas', texto: 'Tus suites se corren solas, sin que nadie se acuerde.' },
  { icono: TrendingUp, titulo: 'Calidad en el tiempo', texto: 'Ves cómo evoluciona cada suite corrida tras corrida.' },
  { icono: Moon, titulo: 'Regresiones encontradas de noche', texto: 'Si algo se rompe, lo sabes antes de abrir la app.' },
]

function Nueva({ cerrar }: { cerrar: () => void }) {
  const { data: suites = [] } = useSuites()
  const refrescar = useRefrescar()
  const [d, setD] = useState({ suite_id: '', frecuencia: 'dia', hora: '03:00', dia: 'Mon', cron: '', slack: false })
  const set = (k: string, v: string | boolean) => setD((x) => ({ ...x, [k]: v }))
  async function crear() {
    try {
      await escribir('/api/programaciones', 'POST', { ...d, suite_id: Number(d.suite_id) })
      await refrescar()
      toast.success('Programación creada')
      cerrar()
    } catch (e) {
      toast.error((e as Error).message)
    }
  }
  return (
    <Card className="mb-6">
      <CardContent className="grid gap-4 p-6 sm:grid-cols-2">
        <label className="block space-y-1.5 text-sm font-medium">Suite
          <select className={campo} value={d.suite_id} onChange={(e) => set('suite_id', e.target.value)}>
            <option value="">Elige una suite</option>
            {suites.map((s) => <option key={s.id} value={s.id}>{s.nombre}</option>)}
          </select>
        </label>
        <label className="block space-y-1.5 text-sm font-medium">Frecuencia
          <select className={campo} value={d.frecuencia} onChange={(e) => set('frecuencia', e.target.value)}>
            {Object.entries(FRECUENCIAS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </label>
        {(d.frecuencia === 'dia' || d.frecuencia === 'semana') && (
          <label className="block space-y-1.5 text-sm font-medium">Hora
            <input type="time" className={campo} value={d.hora} onChange={(e) => set('hora', e.target.value)} />
          </label>
        )}
        {d.frecuencia === 'semana' && (
          <label className="block space-y-1.5 text-sm font-medium">Día
            <select className={campo} value={d.dia} onChange={(e) => set('dia', e.target.value)}>
              {['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo'].map((n, i) => <option key={n} value={DIAS[i]}>{n}</option>)}
            </select>
          </label>
        )}
        {d.frecuencia === 'cron' && (
          <label className="block space-y-1.5 text-sm font-medium">Expresión cron
            <input className={campo} placeholder="0 3 * * 1-5" value={d.cron} onChange={(e) => set('cron', e.target.value)} />
          </label>
        )}
        <label className="flex items-center gap-2 text-sm sm:col-span-2">
          <input type="checkbox" checked={d.slack} onChange={(e) => set('slack', e.target.checked)} />
          Avisar a Slack al terminar
        </label>
        <div className="flex gap-2 sm:col-span-2">
          <Button disabled={!d.suite_id} onClick={crear}>Crear programación</Button>
          <Button variant="outline" onClick={cerrar}>Cancelar</Button>
        </div>
      </CardContent>
    </Card>
  )
}

const cuando = (p: Programacion) =>
  p.frecuencia === 'cron' ? `cron ${p.cron}` : `${FRECUENCIAS[p.frecuencia]}${p.frecuencia === 'hora' ? '' : ` · ${p.hora}`}`

export function Programaciones() {
  const { data = [], isLoading } = useProgramaciones()
  const refrescar = useRefrescar()
  const [nueva, setNueva] = useState(false)
  async function borrar(id: number) {
    try {
      await escribir(`/api/programaciones/${id}`, 'DELETE')
      toast.success('Programación borrada')
      await refrescar()
    } catch (e) {
      toast.error((e as Error).message)
    }
  }
  return (
    <>
      <EncabezadoPagina
        titulo="Programaciones"
        subtitulo="Corre una suite sola, cada hora, a diario, cada semana o con cron."
        acciones={<Button onClick={() => setNueva(true)}><Plus aria-hidden="true" /> Nueva programación</Button>}
      />
      {nueva && <Nueva cerrar={() => setNueva(false)} />}
      {!isLoading && data.length === 0 ? (
        <Vacio
          ilustracion="calendario"
          titulo="Todavía no hay programaciones"
          texto="Programa una suite para que dogfood revise tu app sin que se lo pidas."
          accion={
            <ul className="grid gap-3 text-left sm:grid-cols-3">
              {BENEFICIOS.map(({ icono: I, titulo, texto }) => (
                <li key={titulo} className="max-w-56 space-y-1">
                  <I aria-hidden="true" className="size-5 text-muted-foreground" />
                  <p className="text-sm font-medium">{titulo}</p>
                  <p className="text-sm text-muted-foreground">{texto}</p>
                </li>
              ))}
            </ul>
          }
        />
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Suite</TableHead>
              <TableHead>Cuándo</TableHead>
              <TableHead>Aviso a Slack</TableHead>
              <TableHead><span className="sr-only">Acciones</span></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((p) => (
              <TableRow key={p.id}>
                <TableCell className="font-medium">{p.suite}</TableCell>
                <TableCell>{cuando(p)}</TableCell>
                <TableCell>{p.slack ? 'Sí' : 'No'}</TableCell>
                <TableCell className="text-right">
                  <Button size="icon" variant="ghost" aria-label={`Borrar programación de ${p.suite}`} onClick={() => borrar(p.id)}>
                    <Trash2 aria-hidden="true" />
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </>
  )
}
