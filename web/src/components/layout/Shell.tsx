import { Keyboard, Search } from 'lucide-react'
import { useState, type ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import { SidebarInset, SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar'
import { Toaster } from '@/components/ui/sonner'
import { TooltipProvider } from '@/components/ui/tooltip'
import { BarraLateral } from './BarraLateral'
import { Migas } from './Migas'
import { Paleta } from './Paleta'

/** Marco de todas las pantallas: barra lateral colapsable, encabezado con migas, ⌘K y `?`. */
export function Shell({ children }: { children: ReactNode }) {
  const [paleta, setPaleta] = useState(false)
  const [atajos, setAtajos] = useState(false)
  return (
    <TooltipProvider>
      <SidebarProvider>
        <BarraLateral />
        <SidebarInset className="min-w-0">
          <header className="sticky top-0 z-10 flex h-14 shrink-0 items-center gap-2 border-b bg-background/85 px-4 backdrop-blur">
            <SidebarTrigger className="-ml-1" />
            <Separator orientation="vertical" className="mr-2 h-4" />
            <Migas />
            <div className="ml-auto flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPaleta(true)}
                className="w-9 justify-start px-2 text-muted-foreground sm:w-56"
                aria-label="Abrir la paleta de comandos"
              >
                <Search aria-hidden="true" />
                <span className="hidden flex-1 text-left sm:inline">Buscar…</span>
                <kbd className="hidden rounded border bg-muted px-1.5 font-mono text-[10px] sm:inline">⌘K</kbd>
              </Button>
              <Button variant="ghost" size="icon" onClick={() => setAtajos(true)} aria-label="Atajos de teclado">
                <Keyboard aria-hidden="true" className="sm:hidden" />
                <span aria-hidden="true" className="hidden font-semibold sm:inline">
                  ?
                </span>
              </Button>
            </div>
          </header>
          <div className="mx-auto w-full max-w-7xl flex-1 p-4 md:p-8">{children}</div>
        </SidebarInset>
      </SidebarProvider>
      <Paleta abierta={paleta} setAbierta={setPaleta} atajos={atajos} setAtajos={setAtajos} />
      <Toaster />
    </TooltipProvider>
  )
}
