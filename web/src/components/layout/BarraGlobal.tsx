import { Link, useLocation } from '@tanstack/react-router'
import { ChevronsUpDown } from 'lucide-react'

import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  useSidebar,
} from '@/components/ui/sidebar'
import { Logo } from './Logo'
import { AYUDA, GRUPOS } from './pantallas'
import { SelectorTema } from './SelectorTema'

const activo = (ruta: string, to: string) => (to === '/' ? ruta === '/' : ruta.startsWith(to))

/** Barra global (block `sidebar-07` de shadcn): colapsa a íconos; en móvil es un `sheet`. */
export function BarraGlobal() {
  const ruta = useLocation({ select: (l) => l.pathname })
  const { setOpenMobile } = useSidebar()
  const enlace = ({ to, texto, icono: Icono }: { to: string; texto: string; icono: typeof AYUDA.icono }) => (
    <SidebarMenuItem key={to}>
      <SidebarMenuButton asChild tooltip={texto} isActive={activo(ruta, to)}>
        <Link to={to} onClick={() => setOpenMobile(false)}>
          <Icono aria-hidden="true" />
          <span>{texto}</span>
        </Link>
      </SidebarMenuButton>
    </SidebarMenuItem>
  )
  return (
    <Sidebar collapsible="icon" aria-label="Barra global">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            {/* Selector de espacio: por ahora hay uno solo. */}
            <div className="flex h-12 items-center gap-2 rounded-md border bg-card px-1.5 group-data-[collapsible=icon]:border-0 group-data-[collapsible=icon]:bg-transparent group-data-[collapsible=icon]:px-0">
              <div className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary text-primary-foreground">
                <Logo className="size-5" />
              </div>
              <div className="grid flex-1 leading-tight group-data-[collapsible=icon]:hidden">
                <span className="font-semibold tracking-tight">dogfood</span>
                <span className="text-xs text-muted-foreground">usuarios agénticos</span>
              </div>
              <ChevronsUpDown aria-hidden="true" className="size-4 text-muted-foreground group-data-[collapsible=icon]:hidden" />
            </div>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <nav aria-label="Principal">
          {GRUPOS.map((g) => (
            <SidebarGroup key={g.titulo}>
              {g.titulo && <SidebarGroupLabel>{g.titulo}</SidebarGroupLabel>}
              <SidebarMenu>{g.enlaces.map(enlace)}</SidebarMenu>
            </SidebarGroup>
          ))}
        </nav>
      </SidebarContent>
      <SidebarFooter>
        <SidebarMenu>
          {enlace(AYUDA)}
          <SidebarMenuItem>
            <SelectorTema />
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
