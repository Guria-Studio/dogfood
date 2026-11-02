import { useParams } from '@tanstack/react-router'
import { useState } from 'react'

import { EncabezadoPagina } from '@/components/layout/EncabezadoPagina'
import { Vacio } from '@/components/layout/Vacio'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { type Cambio, type CasoDiff, type PasoDiff, urlCaptura, useDiff } from './api'

const TIPOS = {
  red: 'Red',
  texto: 'Texto',
  visual: 'Visual',
  consola: 'Consola',
} as const
const CLASE_GRAVEDAD = {
  alta: 'text-destructive',
  media: 'text-amber-600',
  baja: 'text-muted-foreground',
} as const

/** Verde 2xx/3xx, rojo 4xx/5xx. */
const claseEstado = (c: number | string | null | undefined) =>
  Number(c) >= 400 ? 'font-semibold text-destructive' : 'font-semibold text-emerald-600'

export function Deslizador({ id, antes, despues }: { id: string; antes: string; despues: string }) {
  const [pos, setPos] = useState(50) // % de la imagen «después» que se ve, desde la derecha
  return (
    <div className="space-y-2">
      <div className="relative overflow-hidden rounded-md border">
        <img src={urlCaptura(id, antes)} alt="Captura antes" className="block w-full" />
        <img
          src={urlCaptura(id, despues)}
          alt="Captura después"
          className="absolute inset-0 size-full"
          style={{ clipPath: `inset(0 0 0 ${pos}%)` }}
        />
        <div className="pointer-events-none absolute inset-y-0 w-0.5 bg-primary" style={{ left: `${pos}%` }} />
      </div>
      <input
        type="range"
        min={0}
        max={100}
        value={pos}
        onChange={(e) => setPos(Number(e.target.value))}
        aria-label="Deslizador antes/después"
        className="w-full"
      />
    </div>
  )
}

function Texto({ c }: { c: Cambio }) {
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      <pre className="whitespace-pre-wrap rounded-md bg-destructive/10 p-2 text-xs" aria-label="Texto antes">
        {c.antes}
      </pre>
      <pre className="whitespace-pre-wrap rounded-md bg-emerald-500/10 p-2 text-xs" aria-label="Texto después">
        {c.despues}
      </pre>
    </div>
  )
}

function TablaRed({ cambios }: { cambios: Cambio[] }) {
  return (
    <Table aria-label="Requests antes y después">
      <TableHeader>
        <TableRow>
          <TableHead>Request</TableHead>
          <TableHead>Antes</TableHead>
          <TableHead>Después</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {cambios.map((c, i) => (
          <TableRow key={i}>
            <TableCell className="font-mono text-xs">
              {c.metodo} {c.ruta}
            </TableCell>
            <TableCell className={c.antes != null ? claseEstado(c.antes) : ''}>{c.antes ?? '—'}</TableCell>
            <TableCell className={c.despues != null ? claseEstado(c.despues) : ''}>{c.despues ?? '—'}</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

function Paso({ id, p }: { id: string; p: PasoDiff }) {
  const tipos = [...new Set(p.cambios.map((c) => c.tipo))]
  const red = p.cambios.filter((c) => c.tipo === 'red')
  return (
    <li className="space-y-3 border-l-2 pl-4" data-paso={p.step_id}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">Paso {p.step_id}</span>
        <span className="text-sm text-muted-foreground">{p.accion}</span>
        {tipos.map((t) => (
          <Badge key={t} variant="secondary">
            {TIPOS[t]}
          </Badge>
        ))}
      </div>
      {red.length > 0 && <TablaRed cambios={red} />}
      {p.cambios
        .filter((c) => c.tipo === 'texto')
        .map((c, i) => (
          <Texto key={i} c={c} />
        ))}
      {p.cambios
        .filter((c) => c.tipo === 'consola')
        .map((c, i) => (
          <p key={i} className={`font-mono text-xs ${CLASE_GRAVEDAD[c.gravedad]}`}>
            Error de consola nuevo: {c.texto}
          </p>
        ))}
      {p.capturas?.antes && p.capturas.despues && (
        <Deslizador id={id} antes={p.capturas.antes} despues={p.capturas.despues} />
      )}
    </li>
  )
}

function Caso({ id, c }: { id: string; c: CasoDiff }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          {c.tc} — {c.titulo}
          <Badge variant={c.resultado === 'cambios' ? 'destructive' : 'outline'}>{c.resultado.replace('_', ' ')}</Badge>
        </CardTitle>
      </CardHeader>
      <CardContent>
        {c.motivo && <p className="text-sm text-muted-foreground">Motivo: {c.motivo}</p>}
        <ol className="space-y-6">
          {c.pasos.map((p) => (
            <Paso key={p.step_id} id={id} p={p} />
          ))}
        </ol>
      </CardContent>
    </Card>
  )
}

export function DetalleDiff() {
  const { id } = useParams({ strict: false }) as { id: string }
  const { data, isPending, isError } = useDiff(id)
  if (isPending) return <Skeleton className="h-40 w-full" />
  if (isError || !data) return <Vacio error titulo="No se pudo cargar el diff" />
  const orden = { cambios: 0, no_alineado: 1, sin_cambios: 2 }
  const casos = [...data.casos].sort((a, b) => orden[a.resultado] - orden[b.resultado] || a.tc.localeCompare(b.tc))
  return (
    <>
      <EncabezadoPagina
        titulo={`${data.base} → ${data.nueva}`}
        subtitulo={`${casos.filter((c) => c.resultado === 'cambios').length} de ${casos.length} casos con cambios`}
      />
      <div className="space-y-4">
        {casos.map((c) => (
          <Caso key={c.tc} id={id} c={c} />
        ))}
      </div>
    </>
  )
}
