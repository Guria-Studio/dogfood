import { useQuery } from '@tanstack/react-query'
import type { LucideIcon } from 'lucide-react'
import { Activity, Bug, CircleCheck, Coins } from 'lucide-react'
import type { ReactNode } from 'react'
import { Bar, CartesianGrid, ComposedChart, Line, XAxis, YAxis } from 'recharts'

import { cliente } from '@/api/cliente'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { type ChartConfig, ChartContainer, ChartLegend, ChartLegendContent, ChartTooltip, ChartTooltipContent } from '@/components/ui/chart'
import { Skeleton } from '@/components/ui/skeleton'
import { usd } from './comun'
import { calcularKpis, useEjecuciones } from './kpis'

function Kpi({ titulo, valor, icono: Icono, pie }: { titulo: string; valor: ReactNode; icono: LucideIcon; pie?: ReactNode }) {
  const id = `kpi-${titulo.replace(/\W+/g, '-')}`
  return (
    <Card role="group" aria-labelledby={id} className="gap-2">
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-0">
        <CardTitle id={id} className="text-sm font-medium tracking-normal text-muted-foreground">
          {titulo}
        </CardTitle>
        <Icono aria-hidden="true" className="size-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div data-kpi-valor className="text-3xl font-semibold tracking-tight tabular-nums">
          {valor}
        </div>
        {pie && <div className="mt-1 text-xs text-muted-foreground">{pie}</div>}
      </CardContent>
    </Card>
  )
}

const GRAFICO = {
  exito: { label: 'Éxito (%)', color: 'hsl(var(--chart-exito))' },
  costo: { label: 'Costo (USD)', color: 'hsl(var(--chart-costo))' },
} satisfies ChartConfig

/** Portada: KPIs y gráfico de las últimas 10 corridas, sobre todas las ejecuciones (sin filtros). */
export function Kpis() {
  const ejecuciones = useEjecuciones()
  const k = calcularKpis(ejecuciones.data ?? [])
  const ultima = useQuery({
    queryKey: ['corrida', k.ultimaCorrida],
    enabled: !!k.ultimaCorrida,
    queryFn: async () => {
      const { data, error } = await cliente.GET('/api/corridas/{corrida_id}', {
        params: { path: { corrida_id: k.ultimaCorrida! } },
      })
      if (!data) throw new Error(String(error))
      return data
    },
  })

  if (ejecuciones.isPending)
    return (
      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-28" />
        ))}
      </div>
    )
  if (!k.total) return null

  const h = k.hallazgos
  return (
    <section aria-label="Resumen" className="mb-8 space-y-4">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Kpi titulo="Tasa de éxito" icono={CircleCheck} valor={`${k.exito}%`} pie="ejecuciones aprobadas por el juez" />
        <Kpi
          titulo="Hallazgos"
          icono={Bug}
          valor={h.fallo + h.rendido + h.no_concluyente}
          pie={
            <span className="flex flex-wrap gap-x-3">
              <span><b className="font-medium text-danger">{h.fallo}</b> alta (fallo)</span>
              <span><b className="font-medium text-warning">{h.rendido}</b> media (rendido)</span>
              <span><b className="font-medium">{h.no_concluyente}</b> baja (no concl.)</span>
            </span>
          }
        />
        <Kpi
          titulo="Costo de la última corrida"
          icono={Coins}
          valor={ultima.data ? usd(ultima.data.resumen.costo_usd) : '—'}
          pie={k.ultimaCorrida && `corrida ${k.ultimaCorrida}`}
        />
        <Kpi titulo="Ejecuciones totales" icono={Activity} valor={k.total} pie={`en ${k.corridas} ${k.corridas === 1 ? 'corrida' : 'corridas'}`} />
      </div>
      <Card>
        <CardHeader>
          <CardTitle>Últimas 10 corridas</CardTitle>
          <CardDescription>Tasa de éxito y costo por corrida</CardDescription>
        </CardHeader>
        <CardContent>
          <ChartContainer config={GRAFICO} className="aspect-auto h-64 w-full">
            <ComposedChart data={k.ultimas} margin={{ left: 4, right: 4 }}>
              <CartesianGrid vertical={false} />
              <XAxis dataKey="corrida" tickLine={false} axisLine={false} tickMargin={8} />
              <YAxis yAxisId="exito" domain={[0, 100]} unit="%" tickLine={false} axisLine={false} width={44} />
              <YAxis yAxisId="costo" orientation="right" tickFormatter={(v: number) => `$${v}`} tickLine={false} axisLine={false} width={48} />
              <ChartTooltip content={<ChartTooltipContent />} />
              <ChartLegend content={<ChartLegendContent />} />
              <Bar yAxisId="exito" dataKey="exito" fill="var(--color-exito)" radius={[4, 4, 0, 0]} maxBarSize={36} />
              <Line yAxisId="costo" dataKey="costo" stroke="var(--color-costo)" strokeWidth={2} dot={{ r: 3 }} type="monotone" />
            </ComposedChart>
          </ChartContainer>
        </CardContent>
      </Card>
    </section>
  )
}
