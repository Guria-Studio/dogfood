import { useState } from 'react'

import { EncabezadoPagina } from '@/components/layout/EncabezadoPagina'
import { Vacio } from '@/components/layout/Vacio'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

import { useActividad, useFuentes, useGuardar, useProyecto } from './api'
import { Ayuda, Interruptor, Tarjeta } from './comun'

export function Fuentes({ slug }: { slug: string }) {
  const { data = [], isLoading } = useFuentes(slug)
  const [q, setQ] = useState('')
  const vistas = data.filter((f) => `${f.nombre} ${f.ruta}`.toLowerCase().includes(q.toLowerCase()))
  return (
    <>
      <EncabezadoPagina titulo="Fuentes" subtitulo="Lo que el agente lee para entender la app: PRD, docs, el repo y las exploraciones." />
      <Input aria-label="Buscar fuentes" placeholder="Buscar fuentes…" value={q} onChange={(e) => setQ(e.target.value)} className="mb-4 max-w-sm" />
      {!isLoading && vistas.length === 0 && q === '' && <Vacio ilustracion="carpeta" titulo="Sin exploraciones todavía" texto="Cuando el agente explore la app, lo que aprenda aparece aquí." />}
      {!isLoading && vistas.length === 0 && q !== '' && <Ayuda>Ninguna fuente coincide con «{q}».</Ayuda>}
      <ul className="max-w-2xl divide-y rounded-lg border bg-card">
        {vistas.map((f) => (
          <li key={f.ruta} className="flex items-center justify-between gap-3 px-4 py-3 text-sm">
            <span className="font-medium">{f.nombre}</span>
            <span className="text-muted-foreground">{f.tipo === 'prd' ? 'PRD' : f.tipo === 'repo' ? 'Repositorio' : f.tipo === 'docs' ? 'Docs' : 'Exploración'}</span>
          </li>
        ))}
      </ul>
    </>
  )
}

const ETIQUETA: Record<string, string> = {
  corrida_lanzada: 'Corrida lanzada',
  corrida_terminada: 'Corrida terminada',
  corrida_cancelada: 'Corrida cancelada',
  issue_publicado: 'Issue publicado',
  ajuste_cambiado: 'Ajuste cambiado',
  proyecto_creado: 'Proyecto creado',
}

export function Actividad({ slug }: { slug: string }) {
  const { data = [], isLoading } = useActividad(slug)
  return (
    <>
      <EncabezadoPagina titulo="Registro de actividad" subtitulo="Lo que pasó en el proyecto: corridas, issues y cambios de ajustes." />
      {!isLoading && data.length === 0 && <Vacio ilustracion="lista" titulo="Todavía no hay actividad" texto="Cada corrida y cada cambio del proyecto queda anotado aquí." />}
      <ol className="max-w-2xl space-y-4 border-l pl-5">
        {data.map((e) => (
          <li key={e.id} className="text-sm">
            <p className="font-medium">{ETIQUETA[e.tipo] ?? e.tipo}{e.detalle && <span className="font-normal text-muted-foreground"> · {e.detalle}</span>}</p>
            <p className="text-muted-foreground">{e.autor} · <time dateTime={e.fecha}>{new Date(e.fecha).toLocaleString('es')}</time></p>
          </li>
        ))}
      </ol>
    </>
  )
}

const flujo = (slug: string, disparador: 'pull_request' | 'push') => `name: dogfood
on:
  ${disparador}:
    branches: [main]
jobs:
  dogfood:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: dogfood ci --target ${slug} --ref \${{ github.sha }}
`

export function AccionGithub({ slug }: { slug: string }) {
  const [disparador, setDisparador] = useState<'pull_request' | 'push'>('pull_request')
  const [copiado, setCopiado] = useState(false)
  const { data: p } = useProyecto(slug)
  const guardar = useGuardar(slug)
  const yaml = flujo(slug, disparador)
  return (
    <>
      <EncabezadoPagina titulo="Acción de GitHub" subtitulo="Corre los casos de prioridad alta en cada cambio y falla el CI si alguno falla." />
      <div className="max-w-2xl space-y-4">
        <Tarjeta titulo="Paso 1 · Agrega el workflow" texto="Crea el archivo .github/workflows/dogfood.yml en tu repositorio.">
          <pre className="overflow-x-auto rounded-md bg-muted p-3 text-xs"><code>{yaml}</code></pre>
          <Button variant="outline" onClick={() => navigator.clipboard?.writeText(yaml).then(() => setCopiado(true))}>
            {copiado ? 'Copiado' : 'Copiar'}
          </Button>
        </Tarjeta>
        <Tarjeta titulo="Paso 2 · Elige el disparador">
          <div role="radiogroup" aria-label="Disparador" className="flex gap-2">
            {([['pull_request', 'Pull request'], ['push', 'Push']] as const).map(([v, t]) => (
              <Button key={v} role="radio" aria-checked={disparador === v} variant={disparador === v ? 'default' : 'outline'} onClick={() => { setDisparador(v); setCopiado(false) }}>{t}</Button>
            ))}
          </div>
        </Tarjeta>
        <Tarjeta titulo="Comentario en el PR" texto="Así se ve lo que dogfood deja en el pull request.">
          <blockquote className="rounded-md border-l-4 bg-muted p-3 text-sm">✅ dogfood: 3/3 casos de prioridad alta pasaron (a1b2c3d)</blockquote>
          {p && (
            <Interruptor
              etiqueta="Comentar en el PR" valor={p.notificaciones.comentar_pr}
              ayuda="Si está apagado, dogfood solo falla o pasa el CI, sin comentar."
              cambiar={(v) => guardar({ notificaciones: { comentar_pr: v } })}
            />
          )}
        </Tarjeta>
      </div>
    </>
  )
}
