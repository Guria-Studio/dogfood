import { useQuery } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { defaultFilter } from 'cmdk'
import { FileText, Keyboard, SunMoon } from 'lucide-react'
import { useEffect, useState } from 'react'

import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandShortcut,
} from '@/components/ui/command'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { buscarDocs } from '@/features/ayuda/api'
import { PANTALLAS } from './pantallas'
import { alternarTema } from './tema'

const ATAJOS: [string[], string][] = [
  [['⌘', 'K'], 'Abrir la paleta de comandos (Ctrl+K en Linux y Windows)'],
  [['?'], 'Ver los atajos de teclado'],
  [['⌘', 'B'], 'Colapsar o expandir la barra lateral'],
  [['←', '→'], 'Paso anterior / siguiente en el detalle de una ejecución'],
  [['Esc'], 'Cerrar diálogos y la paleta'],
]

const enCampo = (t: EventTarget | null) =>
  t instanceof HTMLElement && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))

/** Los documentos de la ayuda ya vienen filtrados por el servidor: siempre se muestran, debajo de las pantallas. */
const filtro = (valor: string, busqueda: string, claves?: string[]) =>
  valor.startsWith('doc:') ? 0.01 : defaultFilter(valor, busqueda, claves)

function useDebounce(valor: string, ms = 200) {
  const [v, setV] = useState(valor)
  useEffect(() => {
    const t = setTimeout(() => setV(valor), ms)
    return () => clearTimeout(t)
  }, [valor, ms])
  return v
}

/** Paleta ⌘K / Ctrl+K y diálogo `?` de atajos. `atajos` lo abre también el botón del encabezado. */
export function Paleta({
  abierta,
  setAbierta,
  atajos,
  setAtajos,
}: {
  abierta: boolean
  setAbierta: (v: boolean | ((v: boolean) => boolean)) => void
  atajos: boolean
  setAtajos: (v: boolean) => void
}) {
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const termino = useDebounce(q.trim())
  const docs = useQuery({
    queryKey: ['ayuda', 'buscar', termino],
    queryFn: () => buscarDocs(termino),
    enabled: abierta && termino.length >= 2,
  })

  useEffect(() => {
    const tecla = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setAbierta((v) => !v)
      } else if (e.key === '?' && !enCampo(e.target)) {
        e.preventDefault()
        setAtajos(true)
      }
    }
    document.addEventListener('keydown', tecla)
    return () => document.removeEventListener('keydown', tecla)
  }, [setAbierta, setAtajos])

  const ejecutar = (accion: () => void) => {
    setAbierta(false)
    setQ('')
    accion()
  }

  return (
    <>
      <CommandDialog
        open={abierta}
        onOpenChange={(v) => {
          setAbierta(v)
          if (!v) setQ('')
        }}
        filter={filtro}
      >
        <CommandInput placeholder="Ir a una pantalla, buscar en la ayuda…" value={q} onValueChange={setQ} />
        <CommandList>
          <CommandEmpty>Sin resultados.</CommandEmpty>
          <CommandGroup heading="Ir a">
            {PANTALLAS.map(({ to, texto, icono: Icono }) => (
              <CommandItem key={to} value={texto} onSelect={() => ejecutar(() => navigate({ to }))}>
                <Icono aria-hidden="true" />
                {texto}
              </CommandItem>
            ))}
          </CommandGroup>
          <CommandGroup heading="Acciones">
            <CommandItem value="Alternar tema" keywords={['oscuro', 'claro']} onSelect={() => ejecutar(alternarTema)}>
              <SunMoon aria-hidden="true" />
              Alternar tema claro / oscuro
            </CommandItem>
            <CommandItem value="Atajos de teclado" keywords={['teclas']} onSelect={() => ejecutar(() => setAtajos(true))}>
              <Keyboard aria-hidden="true" />
              Atajos de teclado
              <CommandShortcut>?</CommandShortcut>
            </CommandItem>
          </CommandGroup>
          {!!docs.data?.length && (
            <CommandGroup heading="En la ayuda">
              {docs.data.map((d) => (
                <CommandItem
                  key={d.slug}
                  value={`doc:${d.slug}`}
                  onSelect={() => ejecutar(() => navigate({ to: '/ayuda/$slug', params: { slug: d.slug } }))}
                >
                  <FileText aria-hidden="true" />
                  <span className="truncate">{d.titulo}</span>
                </CommandItem>
              ))}
            </CommandGroup>
          )}
        </CommandList>
      </CommandDialog>
      <Dialog open={atajos} onOpenChange={setAtajos}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Atajos de teclado</DialogTitle>
            <DialogDescription>Funcionan en cualquier pantalla del panel.</DialogDescription>
          </DialogHeader>
          <dl className="divide-y text-sm">
            {ATAJOS.map(([teclas, texto]) => (
              <div key={texto} className="flex items-center justify-between gap-4 py-2">
                <dt className="text-muted-foreground">{texto}</dt>
                <dd className="flex gap-1">
                  {teclas.map((t) => (
                    <kbd key={t} className="rounded border bg-muted px-1.5 py-0.5 font-mono text-xs">
                      {t}
                    </kbd>
                  ))}
                </dd>
              </div>
            ))}
          </dl>
        </DialogContent>
      </Dialog>
    </>
  )
}
