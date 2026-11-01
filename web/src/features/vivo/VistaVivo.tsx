import { useEffect, useState } from 'react'

import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog'
import { type Ejecucion, useVista } from './useVista'

function Latencia({ ts }: { ts: number | null }) {
  const [ahora, setAhora] = useState(() => Date.now())
  useEffect(() => {
    const t = setInterval(() => setAhora(Date.now()), 500)
    return () => clearInterval(t)
  }, [])
  return <span>{ts ? `latencia ${Math.max(0, ahora - ts)} ms` : 'sin frames'}</span>
}

function Contenido({ e, grande }: { e: Ejecucion; grande?: boolean }) {
  return (
    <>
      <div className="flex justify-between gap-2 text-sm">
        <strong>{e.persona}</strong>
        <span>{e.escenario}</span>
      </div>
      <div className="text-muted-foreground text-xs">
        paso {e.paso} · <Latencia ts={e.tsFrame} /> · resultado: {e.resultado ?? 'en curso'}
      </div>
      <div className="mt-2 flex gap-2">
        {e.frame ? (
          <img src={e.frame} alt={`Pantalla de ${e.persona}`} className="w-3/5 rounded bg-black" />
        ) : (
          <div className="w-3/5 rounded bg-black" />
        )}
        <ol
          aria-label="Razonamiento"
          className={`flex-1 list-none space-y-1 overflow-auto text-xs ${grande ? 'max-h-[70vh] text-sm' : 'max-h-64'}`}
        >
          {e.pasos.map((p, i) => (
            <li key={`${e.pasos.length - i}`}>{p}</li>
          ))}
        </ol>
      </div>
    </>
  )
}

export function VistaVivo() {
  const { conectado, ejecuciones } = useVista()
  const [ampliada, setAmpliada] = useState<string | null>(null)
  const sel = ejecuciones.find((e) => e.id === ampliada)

  return (
    <>
      <p className="text-muted-foreground mb-3 text-sm">{conectado ? 'Conectado' : 'Reconectando…'}</p>
      {!conectado && ejecuciones.length === 0 && (
        <div role="alert" className="rounded-lg border p-4">
          <p>No hay una corrida con vista activa.</p>
          <p className="text-muted-foreground mt-2 text-sm">Lánzala con:</p>
          <pre className="bg-muted mt-1 rounded p-2 text-sm">
            <code>uv run dogfood run --target predicts --vista</code>
          </pre>
        </div>
      )}
      <div className="grid grid-cols-[repeat(auto-fill,minmax(360px,1fr))] gap-4">
        {ejecuciones.map((e) => (
          <button
            key={e.id}
            type="button"
            data-testid="tarjeta"
            onClick={() => setAmpliada(e.id)}
            className="rounded-lg border p-3 text-left"
          >
            <Contenido e={e} />
          </button>
        ))}
      </div>
      <Dialog open={!!sel} onOpenChange={(o) => !o && setAmpliada(null)}>
        <DialogContent className="max-w-5xl sm:max-w-5xl">
          <DialogTitle>{sel?.persona}</DialogTitle>
          <DialogDescription className="sr-only">Ejecución ampliada</DialogDescription>
          {sel && <Contenido e={sel} grande />}
        </DialogContent>
      </Dialog>
    </>
  )
}
