import { Link, useLocation } from '@tanstack/react-router'

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
import { GRUPOS } from './pantallas'
import { SelectorTema } from './SelectorTema'

const activo = (ruta: string, to: string) =>
  to === '/' ? ruta === '/' || ruta.startsWith('/corridas') || ruta.startsWith('/ejecuciones') : ruta.startsWith(to)

/** Barra lateral (block `sidebar-07` de shadcn): colapsa a íconos; en móvil es un `sheet`. */
export function BarraLateral() {
  const ruta = useLocation({ select: (l) => l.pathname })
  const { setOpenMobile } = useSidebar()
  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <SidebarMenu>
          <SidebarMenuItem>
            <div className="flex h-12 items-center gap-2 px-1 group-data-[collapsible=icon]:px-0">
              <div className="grid size-8 shrink-0 place-items-center rounded-lg bg-primary text-primary-foreground">
                <Logo className="size-5" />
              </div>
              <div className="grid leading-tight group-data-[collapsible=icon]:hidden">
                <span className="font-semibold tracking-tight">dogfood</span>
                <span className="text-xs text-muted-foreground">usuarios agénticos</span>
              </div>
            </div>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarHeader>
      <SidebarContent>
        <nav aria-label="Principal">
          {GRUPOS.map((g) => (
            <SidebarGroup key={g.titulo}>
              <SidebarGroupLabel>{g.titulo}</SidebarGroupLabel>
              <SidebarMenu>
                {g.enlaces.map(({ to, texto, icono: Icono }) => (
                  <SidebarMenuItem key={to}>
                    <SidebarMenuButton asChild tooltip={texto} isActive={activo(ruta, to)}>
                      <Link to={to} onClick={() => setOpenMobile(false)}>
                        <Icono aria-hidden="true" />
                        <span>{texto}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroup>
          ))}
        </nav>
      </SidebarContent>
      <SidebarFooter>
        <SidebarMenu>
          <SidebarMenuItem>
            <SelectorTema />
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
