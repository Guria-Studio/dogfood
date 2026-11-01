import { Menu } from 'lucide-react'
import { useState, type ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetDescription, SheetTitle, SheetTrigger } from '@/components/ui/sheet'
import { Toaster } from '@/components/ui/sonner'
import { TooltipProvider } from '@/components/ui/tooltip'
import { BarraLateral } from './BarraLateral'

/** Marco de todas las pantallas: barra lateral fija en escritorio, `sheet` en móvil. */
export function Shell({ children }: { children: ReactNode }) {
  const [abierto, setAbierto] = useState(false)
  return (
    <TooltipProvider>
      <div className="min-h-screen md:flex">
        <aside className="sticky top-0 hidden h-screen w-60 shrink-0 border-r bg-card p-4 md:block">
          <BarraLateral />
        </aside>
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="flex items-center gap-2 border-b bg-card p-2 md:hidden">
            <Sheet open={abierto} onOpenChange={setAbierto}>
              <SheetTrigger asChild>
                <Button variant="ghost" size="icon" aria-label="Abrir menú">
                  <Menu aria-hidden="true" />
                </Button>
              </SheetTrigger>
              <SheetContent>
                <SheetTitle className="sr-only">Menú</SheetTitle>
                <SheetDescription className="sr-only">Navegación del panel</SheetDescription>
                <BarraLateral alNavegar={() => setAbierto(false)} />
              </SheetContent>
            </Sheet>
            <span className="font-semibold">dogfood</span>
          </div>
          <main className="flex-1 p-4 md:p-8">{children}</main>
        </div>
      </div>
      <Toaster />
    </TooltipProvider>
  )
}
