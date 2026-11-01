import { useEffect, useState } from 'react'

/** Evento del `/ws` de la vista (`EventoVivo` en src/dogfood/eventos.py). */
export interface EventoVivo {
  ejecucion_id: string
  tipo: 'inicio' | 'paso' | 'frame' | 'fin'
  n_paso: number
  persona: string
  escenario: string
  paso_contrato: string
  razonamiento: string
  accion: string
  resultado: string | null
  frame_jpeg_b64?: string
  ts: string
}

export interface Ejecucion {
  id: string
  persona: string
  escenario: string
  paso: number
  frame: string | null
  tsFrame: number | null
  pasos: string[]
  resultado: string | null
}

const MAX_PASOS = 30
export const REINTENTO_MS = 5000

function aplicar(previo: Ejecucion | undefined, ev: EventoVivo): Ejecucion {
  const e: Ejecucion = previo ?? {
    id: ev.ejecucion_id,
    persona: '',
    escenario: '',
    paso: 0,
    frame: null,
    tsFrame: null,
    pasos: [],
    resultado: null,
  }
  const sig = { ...e, persona: ev.persona || e.persona, escenario: ev.escenario || e.escenario }
  if (ev.tipo === 'paso') {
    sig.paso = ev.n_paso
    sig.pasos = [`${ev.paso_contrato} → ${ev.accion} → ${ev.razonamiento}`, ...e.pasos].slice(0, MAX_PASOS)
  } else if (ev.tipo === 'frame' && ev.frame_jpeg_b64) {
    sig.frame = `data:image/jpeg;base64,${ev.frame_jpeg_b64}`
    sig.tsFrame = new Date(ev.ts).getTime()
  } else if (ev.tipo === 'fin') {
    sig.resultado = ev.resultado ?? '—'
  }
  return sig
}

/** Se conecta a `/ws` del mismo origen; si se cae (o no conecta) reintenta cada 5 s. */
export function useVista() {
  const [conectado, setConectado] = useState(false)
  const [ejecuciones, setEjecuciones] = useState<Record<string, Ejecucion>>({})

  useEffect(() => {
    let ws: WebSocket | undefined
    let timer: ReturnType<typeof setTimeout> | undefined
    let activo = true
    const conectar = () => {
      const proto = location.protocol === 'https:' ? 'wss://' : 'ws://'
      ws = new WebSocket(`${proto}${location.host}/ws`)
      ws.onopen = () => setConectado(true)
      ws.onmessage = (m) => {
        const ev = JSON.parse(m.data) as EventoVivo
        setEjecuciones((s) => ({ ...s, [ev.ejecucion_id]: aplicar(s[ev.ejecucion_id], ev) }))
      }
      ws.onclose = () => {
        setConectado(false)
        if (activo) timer = setTimeout(conectar, REINTENTO_MS)
      }
    }
    conectar()
    return () => {
      activo = false
      clearTimeout(timer)
      if (ws) {
        ws.onclose = null
        ws.close()
      }
    }
  }, [])

  return { conectado, ejecuciones: Object.values(ejecuciones) }
}
