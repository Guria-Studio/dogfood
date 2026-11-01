import { ChevronLeft, ChevronRight } from 'lucide-react'
import { useEffect, useState } from 'react'

import type { components } from '@/api/schema'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { cn } from '@/lib/utils'
import { lineaConsola, lineaRed } from './lineas'

export type Paso = components['schemas']['PasoVista']
export function Bloque({ lineas, vacio }: { lineas: string[]; vacio: string }) {
  if (!lineas.length) return <p className="text-sm text-muted-foreground">{vacio}</p>
  return (
    <pre className="max-h-80 overflow-auto rounded-md bg-muted p-3 text-xs whitespace-pre-wrap">
      {lineas.join('\n')}
    </pre>
  )
}

function Campo({ titulo, texto }: { titulo: string; texto: string }) {
  if (!texto) return null
  return (
    <div>
      <dt className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{titulo}</dt>
      <dd className="mt-0.5 text-sm whitespace-pre-wrap">{texto}</dd>
    </div>
  )
}

/** Un paso a la vez: botones, línea de tiempo clicable y ← / → del teclado. */
export function VisorPasos({ pasos }: { pasos: Paso[] }) {
  const [actual, setActual] = useState(0)
  const ir = (i: number) => setActual(Math.max(0, Math.min(pasos.length - 1, i)))

  useEffect(() => {
    function tecla(ev: KeyboardEvent) {
      const t = ev.target as HTMLElement | null
      // No robar las flechas a campos, pestañas ni al diálogo abierto.
      if (t?.closest('input, select, textarea, [role="dialog"], [role="tablist"]')) return
      if (ev.key === 'ArrowLeft') setActual((i) => Math.max(0, i - 1))
      if (ev.key === 'ArrowRight') setActual((i) => Math.min(pasos.length - 1, i + 1))
    }
    window.addEventListener('keydown', tecla)
    return () => window.removeEventListener('keydown', tecla)
  }, [pasos.length])

  if (!pasos.length) return <p className="text-muted-foreground">Sin pasos registrados.</p>
  const p = pasos[Math.min(actual, pasos.length - 1)]

  return (
    <Card>
      <CardHeader className="gap-3">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>
            Paso {p.n} · {p.pantalla}
          </CardTitle>
          <div className="flex gap-2">
            <Button variant="outline" size="sm" onClick={() => ir(actual - 1)} disabled={actual === 0}>
              <ChevronLeft aria-hidden="true" /> Anterior
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => ir(actual + 1)}
              disabled={actual === pasos.length - 1}
            >
              Siguiente <ChevronRight aria-hidden="true" />
            </Button>
          </div>
        </div>
        <nav aria-label="Línea de tiempo" className="flex flex-wrap gap-1">
          {pasos.map((x, i) => (
            <button
              key={x.n}
              type="button"
              onClick={() => ir(i)}
              aria-current={i === actual ? 'step' : undefined}
              aria-label={`Paso ${x.n}`}
              title={x.pantalla}
              className={cn(
                'size-8 rounded-md border text-xs font-medium transition-colors hover:bg-accent',
                i === actual && 'border-primary bg-primary text-primary-foreground hover:bg-primary',
              )}
            >
              {x.n}
            </button>
          ))}
        </nav>
      </CardHeader>
      <CardContent className="grid gap-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,2fr)]">
        {p.captura ? (
          <img
            src={p.captura}
            alt={`Captura del paso ${p.n}`}
            className="w-full rounded-md border object-contain"
          />
        ) : (
          <div className="grid min-h-48 place-items-center rounded-md border border-dashed text-sm text-muted-foreground">
            Sin captura
          </div>
        )}
        <div className="min-w-0 space-y-4">
          <dl className="space-y-3">
            <Campo titulo="Acción" texto={p.accion} />
            <Campo titulo="Razonamiento" texto={p.razonamiento} />
            <Campo titulo="Paso del contrato" texto={p.paso_contrato} />
            <Campo titulo="Esperado" texto={p.esperado} />
            <Campo titulo="Observado" texto={p.observado} />
            <Campo titulo="URL" texto={p.url} />
          </dl>
          <Tabs defaultValue="consola" key={p.n}>
            <TabsList>
              <TabsTrigger value="consola">Consola ({p.consola.length})</TabsTrigger>
              <TabsTrigger value="red">Red ({p.red.length})</TabsTrigger>
            </TabsList>
            <TabsContent value="consola" className="mt-3">
              <Bloque lineas={p.consola.map(lineaConsola)} vacio="Sin mensajes de consola en este paso." />
            </TabsContent>
            <TabsContent value="red" className="mt-3">
              <Bloque lineas={p.red.map(lineaRed)} vacio="Sin pedidos de red en este paso." />
            </TabsContent>
          </Tabs>
        </div>
      </CardContent>
    </Card>
  )
}
