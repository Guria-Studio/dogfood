import { Link } from '@tanstack/react-router'
import { CircleHelp, Eye, History, ListChecks, Smartphone } from 'lucide-react'

import { SelectorTema } from './SelectorTema'

const ENLACES = [
  { to: '/', texto: 'Corridas', icono: History },
  { to: '/recorridos', texto: 'Recorridos', icono: ListChecks },
  { to: '/dispositivos', texto: 'Dispositivos', icono: Smartphone },
  { to: '/vista', texto: 'Vista en vivo', icono: Eye },
  { to: '/ayuda', texto: 'Ayuda', icono: CircleHelp },
] as const

export function BarraLateral({ alNavegar }: { alNavegar?: () => void }) {
  return (
    <div className="flex h-full flex-col gap-4">
      <div className="px-3 pt-1 text-lg font-semibold">dogfood</div>
      <nav aria-label="Principal" className="flex flex-1 flex-col gap-1">
        {ENLACES.map(({ to, texto, icono: Icono }) => (
          <Link
            key={to}
            to={to}
            onClick={alNavegar}
            activeOptions={{ exact: to === '/' }}
            className="flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground data-[status=active]:bg-accent data-[status=active]:text-accent-foreground"
          >
            <Icono aria-hidden="true" className="size-4 shrink-0" />
            {texto}
          </Link>
        ))}
      </nav>
      <SelectorTema />
    </div>
  )
}
