import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { Copy, Download } from 'lucide-react'

import { cliente } from '@/api/cliente'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { toast } from '@/components/ui/sonner'
import { BadgeResultado, duracion, fecha, usd } from '@/features/corridas/comun'

const GRAVEDADES = ['critica', 'alta', 'media', 'baja'] as const
const ETIQUETA: Record<string, string> = { aprobado: 'Aprobados', fallo: 'Fallidos', no_concluyente: 'No concluyentes' }

/** Texto corto para Slack o un PR: tasa de éxito, hallazgos altos y críticos con link y link al reporte. */
export function resumenTexto(o: {
  id: string
  exito: number
  conteos: Record<string, number>
  graves: { titulo: string; gravedad: string; ejecucion_id: string | null }[]
  origen: string
}) {
  const c = o.conteos
  const lineas = [
    `Reporte dogfood ${o.id}: éxito ${o.exito}% (${c.aprobado ?? 0} aprobados, ${c.fallo ?? 0} fallidos, ${c.no_concluyente ?? 0} no concluyentes)`,
    ...o.graves.map(
      (h) => `• [${h.gravedad}] ${h.titulo}${h.ejecucion_id ? ` — ${o.origen}/ejecuciones/${h.ejecucion_id}` : ''}`,
    ),
    `Reporte completo: ${o.origen}/corridas/${o.id}/reporte`,
  ]
  return lineas.join('\n')
}

function Radial({ pct }: { pct: number }) {
  const r = 52
  const c = 2 * Math.PI * r
  return (
    <svg viewBox="0 0 128 128" className="h-36 w-36" role="img" aria-label={`Tasa de éxito ${pct}%`}>
      <circle cx="64" cy="64" r={r} fill="none" strokeWidth="12" className="stroke-muted" />
      <circle
        cx="64" cy="64" r={r} fill="none" strokeWidth="12" strokeLinecap="round"
        className="stroke-green-600" strokeDasharray={`${(c * pct) / 100} ${c}`}
        transform="rotate(-90 64 64)"
      />
      <text x="64" y="72" textAnchor="middle" className="fill-foreground text-3xl font-semibold">{pct}%</text>
    </svg>
  )
}

export function PantallaReporte({ id }: { id: string }) {
  const corrida = useQuery({
    queryKey: ['corrida', id],
    queryFn: async () => {
      const { data, error } = await cliente.GET('/api/corridas/{corrida_id}', { params: { path: { corrida_id: id } } })
      if (!data) throw new Error(String(error))
      return data
    },
  })
  const reporte = useQuery({
    queryKey: ['reporte', id],
    queryFn: async () => {
      const { data, error } = await cliente.GET('/api/corridas/{corrida_id}/reporte', { params: { path: { corrida_id: id } } })
      if (!data) throw new Error(String(error))
      return data
    },
  })
  if (corrida.isError || reporte.isError) return <p>No se encontró la corrida {id}.</p>
  if (!corrida.data || !reporte.data) return <Skeleton data-testid="cargando" className="h-40 w-full" />

  const { resumen: r } = corrida.data
  const { hallazgos, fallidos, opiniones } = reporte.data
  const conteos = r.por_resultado
  const exito = r.ejecuciones ? Math.round(((conteos.aprobado ?? 0) / r.ejecuciones) * 100) : 0
  const segundos = r.fin ? (Date.parse(r.fin) - Date.parse(r.inicio)) / 1000 : null
  const graves = hallazgos.filter((h) => h.gravedad === 'alta' || h.gravedad === 'critica')

  const copiar = () => {
    const texto = resumenTexto({ id, exito, conteos, graves, origen: window.location.origin })
    navigator.clipboard.writeText(texto).then(
      () => toast.success('Resumen copiado'),
      () => toast.error('No se pudo copiar'),
    )
  }

  return (
    <article data-reporte-listo className="mx-auto max-w-3xl space-y-8 print:max-w-none">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-serif text-4xl">Reporte de la corrida {id}</h1>
          <p className="text-sm text-muted-foreground">
            {r.objetivo}@{r.ref} · versión {r.version} · {fecha(r.inicio)}
          </p>
        </div>
        <div className="flex gap-2 print:hidden">
          <Button variant="outline" onClick={copiar}>
            <Copy aria-hidden="true" /> Copiar resumen
          </Button>
          <Button asChild>
            <a href={`/api/corridas/${id}/reporte.pdf`} download>
              <Download aria-hidden="true" /> Descargar PDF
            </a>
          </Button>
        </div>
      </header>

      <section className="flex flex-wrap items-center gap-8 break-inside-avoid">
        <Radial pct={exito} />
        <dl className="grid grid-cols-2 gap-x-8 gap-y-1 text-sm">
          {Object.entries(conteos).map(([res, n]) => (
            <div key={res} className="contents">
              <dt>{ETIQUETA[res] ?? res}</dt>
              <dd data-estado={res} className="font-semibold">{n}</dd>
            </div>
          ))}
          <dt>Costo</dt>
          <dd className="font-semibold">{usd(r.costo_usd)}</dd>
          <dt>Duración</dt>
          <dd className="font-semibold">{segundos === null ? '—' : duracion(segundos)}</dd>
        </dl>
      </section>

      <section className="break-inside-avoid">
        <h2 className="mb-2 text-xl font-semibold">Hallazgos por gravedad</h2>
        <p className="mb-3 flex flex-wrap gap-4 text-sm">
          {GRAVEDADES.map((g) => (
            <span key={g} data-gravedad={g}>
              {g}: <strong>{hallazgos.filter((h) => h.gravedad === g).length}</strong>
            </span>
          ))}
        </p>
        <ul className="space-y-2 text-sm">
          {hallazgos.map((h) => (
            <li key={h.id} className="break-inside-avoid rounded-md border p-3">
              <strong>[{h.gravedad}]</strong> {h.titulo} <span className="text-muted-foreground">· {h.pantalla}</span>
              {h.sugerencia && <p className="mt-1 text-muted-foreground">Sugerencia: {h.sugerencia.cambio.slice(0, 200)}</p>}
            </li>
          ))}
          {hallazgos.length === 0 && <li className="text-muted-foreground">Sin hallazgos.</li>}
        </ul>
      </section>

      <section>
        <h2 className="mb-2 text-xl font-semibold">Casos fallidos</h2>
        {fallidos.length === 0 ? (
          <p className="text-sm text-muted-foreground">Ningún caso falló.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b text-left">
                <th className="py-1">Captura</th><th>Caso</th><th>Persona</th><th>Resultado</th>
              </tr>
            </thead>
            <tbody>
              {fallidos.map((f) => (
                <tr key={f.ejecucion_id} className="break-inside-avoid border-b">
                  <td className="py-1">
                    {f.miniatura ? <img src={f.miniatura} alt="" className="h-12 w-20 rounded object-cover" /> : '—'}
                  </td>
                  <td>
                    <Link to="/ejecuciones/$id" params={{ id: f.ejecucion_id }} className="underline">{f.titulo}</Link>
                  </td>
                  <td>{f.persona}</td>
                  <td><BadgeResultado resultado={f.resultado} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section>
        <h2 className="mb-2 text-xl font-semibold">Opinión de los usuarios por pantalla</h2>
        {opiniones.length === 0 && <p className="text-sm text-muted-foreground">Sin fricciones registradas.</p>}
        {opiniones.map((o) => (
          <div key={o.pantalla} className="mb-4 break-inside-avoid text-sm">
            <h3 className="font-medium">{o.pantalla} <span className="text-muted-foreground">· {o.total} fricciones</span></h3>
            {o.citas.map((c, i) => (
              <blockquote key={i} className="mt-1 border-l-2 pl-3 italic">
                «{c.cita || c.texto}»
              </blockquote>
            ))}
          </div>
        ))}
      </section>
    </article>
  )
}
