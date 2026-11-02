import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Sheet, SheetContent, SheetDescription, SheetTitle } from '@/components/ui/sheet'
import { useMapa } from '@/features/mapa/api'
import { editarEscenario, type EscenarioProyecto, useEscenarios } from './api'

/** Campo de texto que se guarda al salir de él, solo si cambió. */
function Editable({ valor, etiqueta, guardar }: { valor: string; etiqueta: string; guardar: (v: string) => void }) {
  const [v, setV] = useState(valor)
  return (
    <Input
      aria-label={etiqueta}
      value={v}
      onChange={(e) => setV(e.target.value)}
      onBlur={() => v.trim() !== '' && v !== valor && guardar(v)}
    />
  )
}

/** Franja «N escenarios propuestos para revisar» y la tabla de revisión (nada corre hasta aceptar). */
export function RevisarPlan({ slug }: { slug: string }) {
  const qc = useQueryClient()
  const borradores = useEscenarios(slug, 'borrador')
  const mapa = useMapa(slug)
  const [abierto, setAbierto] = useState(false)
  const [marcados, setMarcados] = useState<Set<string>>(new Set())
  const [flujo, setFlujo] = useState<string | null>(null)
  const [error, setError] = useState('')
  const lista = borradores.data ?? []
  if (lista.length === 0 && !abierto) return null

  const refrescar = () => qc.invalidateQueries({ queryKey: ['escenarios', slug] })
  const probar = async (f: () => Promise<unknown>) => {
    setError('')
    try {
      await f()
      await refrescar()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }
  const cerrar = async (estado: 'aceptado' | 'descartado') => {
    const ids = [...marcados] // Descartar sin marcar nada solo cierra la revisión
    await probar(() => Promise.all(ids.map((id) => editarEscenario(slug, id, { estado }))))
    setMarcados(new Set())
    setAbierto(false)
  }
  const alternar = (id: string) =>
    setMarcados((m) => {
      const n = new Set(m)
      if (!n.delete(id)) n.add(id)
      return n
    })
  const pantallasDe = (e: EscenarioProyecto) => (e.superficies ?? []).map((s) => mapa.data?.pantallas.find((p) => p.path === s || p.titulo === s)?.path ?? s)

  return (
    <>
      {lista.length > 0 && (
        <div role="status" className="mb-4 flex items-center justify-between gap-3 rounded-lg border border-amber-300 bg-amber-50 px-4 py-2.5 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
          <span>{lista.length} {lista.length === 1 ? 'escenario propuesto' : 'escenarios propuestos'} para revisar</span>
          <Button size="sm" onClick={() => setAbierto(true)}>Revisar plan</Button>
        </div>
      )}
      <Sheet open={abierto} onOpenChange={setAbierto}>
        <SheetContent side="right" className="w-[min(72rem,95vw)] max-w-none overflow-y-auto">
          <SheetTitle>Revisar el plan</SheetTitle>
          <SheetDescription>Edita, marca los que valen y acepta. Nada corre hasta que aceptes.</SheetDescription>
          {error && <p role="alert" className="mt-2 text-sm text-danger">{error}</p>}
          <table className="mt-4 w-full text-sm">
            <thead>
              <tr className="text-left text-xs text-muted-foreground">
                <th className="w-8" /><th className="w-28">Prioridad</th><th>Título</th><th>Objetivo</th><th />
              </tr>
            </thead>
            <tbody>
              {lista.map((e) => (
                <tr key={e.id} data-escenario={e.id} className="border-t align-top">
                  <td className="py-2"><input type="checkbox" aria-label={`Elegir ${e.titulo}`} checked={marcados.has(e.id)} onChange={() => alternar(e.id)} /></td>
                  <td className="py-2 pr-2">
                    <select aria-label={`Prioridad de ${e.titulo}`} className="rounded-md border bg-background p-1.5" value={e.prioridad} onChange={(ev) => probar(() => editarEscenario(slug, e.id, { prioridad: ev.target.value as 'alta' | 'media' }))}>
                      <option value="alta">alta</option>
                      <option value="media">media</option>
                    </select>
                  </td>
                  <td className="py-2 pr-2"><Editable etiqueta={`Título de ${e.titulo}`} valor={e.titulo} guardar={(v) => probar(() => editarEscenario(slug, e.id, { titulo: v }))} /></td>
                  <td className="py-2 pr-2"><Editable etiqueta={`Objetivo de ${e.titulo}`} valor={e.objetivo} guardar={(v) => probar(() => editarEscenario(slug, e.id, { objetivo: v }))} /></td>
                  <td className="py-2"><Button variant="ghost" size="sm" onClick={() => setFlujo(flujo === e.id ? null : e.id)}>Ver flujo</Button></td>
                </tr>
              ))}
            </tbody>
          </table>
          {lista.filter((e) => e.id === flujo).map((e) => (
            <ol key={e.id} aria-label={`Flujo de ${e.titulo}`} className="mt-4 flex flex-wrap gap-3">
              {pantallasDe(e).map((p) => <li key={p} className="rounded border bg-muted px-2 py-1 font-mono text-xs">{p}</li>)}
              {pantallasDe(e).length === 0 && <li className="text-sm text-muted-foreground">Sin pantallas asociadas.</li>}
            </ol>
          ))}
          <div className="mt-6 flex justify-end gap-2">
            <Button variant="ghost" onClick={() => cerrar('descartado')}>Descartar</Button>
            <Button disabled={marcados.size === 0} onClick={() => cerrar('aceptado')}>Aceptar seleccionados</Button>
          </div>
        </SheetContent>
      </Sheet>
    </>
  )
}
