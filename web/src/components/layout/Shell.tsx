import { useLocation, useParams } from '@tanstack/react-router'
import { Keyboard, Link2, Search, Share2 } from 'lucide-react'
import { useState, type ReactNode } from 'react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { SidebarInset, SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar'
import { Toaster } from '@/components/ui/sonner'
import { TooltipProvider } from '@/components/ui/tooltip'
import { BarraGlobal } from './BarraGlobal'
import { BarraProyecto } from './BarraProyecto'
import { Migas } from './Migas'
import { Paleta } from './Paleta'

/** Dominio público del panel: «Compartir» copia el link con este origen. */
export const ORIGEN_PUBLICO = 'https://dogfood.knaimero.app'

async function copiar(texto: string, aviso: string) {
  try {
    await navigator.clipboard.writeText(texto)
    toast.success(aviso)
  } catch {
    toast.error('No se pudo copiar el link')
  }
}

/** Marco de todas las pantallas: barra global, barra de proyecto (si hay), encabezado con migas, ⌘K y `?`. */
export function Shell({ children }: { children: ReactNode }) {
  const [paleta, setPaleta] = useState(false)
  const [atajos, setAtajos] = useState(false)
  const { proyecto } = useParams({ strict: false }) as { proyecto?: string }
  const ruta = useLocation({ select: (l) => l.href })
  const contenido = <div className="mx-auto w-full max-w-7xl min-w-0 flex-1 p-4 md:p-8">{children}</div>
  return (
    <TooltipProvider>
      <SidebarProvider>
        <BarraGlobal />
        <SidebarInset className="min-w-0">
          <header className="sticky top-0 print:hidden z-10 flex h-14 shrink-0 items-center gap-2 border-b bg-background/85 px-4 backdrop-blur">
            <SidebarTrigger className="-ml-1" />
            <Separator orientation="vertical" className="mr-2 h-4" />
            <Migas />
            <div className="ml-auto flex items-center gap-1.5">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPaleta(true)}
                className="w-9 justify-start px-2 text-muted-foreground lg:w-48"
                aria-label="Abrir la paleta de comandos"
              >
                <Search aria-hidden="true" />
                <span className="hidden flex-1 text-left lg:inline">Buscar…</span>
                <kbd className="hidden rounded border bg-muted px-1.5 font-mono text-[10px] lg:inline">⌘K</kbd>
              </Button>
              <Button variant="outline" size="sm" onClick={() => copiar(ORIGEN_PUBLICO + ruta, 'Link público copiado')}>
                <Share2 aria-hidden="true" />
                <span className="hidden sm:inline">Compartir</span>
              </Button>
              <Button
                variant="ghost"
                size="icon"
                aria-label="Copiar link"
                onClick={() => copiar(window.location.href, 'Link copiado')}
              >
                <Link2 aria-hidden="true" />
              </Button>
              <Button variant="ghost" size="icon" onClick={() => setAtajos(true)} aria-label="Atajos de teclado">
                <Keyboard aria-hidden="true" className="sm:hidden" />
                <span aria-hidden="true" className="hidden font-semibold sm:inline">
                  ?
                </span>
              </Button>
            </div>
          </header>
          {proyecto ? (
            <div className="flex flex-1 flex-col md:flex-row">
              <BarraProyecto proyecto={proyecto} />
              {contenido}
            </div>
          ) : (
            contenido
          )}
        </SidebarInset>
      </SidebarProvider>
      <Paleta abierta={paleta} setAbierta={setPaleta} atajos={atajos} setAtajos={setAtajos} />
      <Toaster />
    </TooltipProvider>
  )
}
