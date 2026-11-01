import { Moon, Sun } from 'lucide-react'

import { SidebarMenuButton } from '@/components/ui/sidebar'
import { useTema } from './tema'

export function SelectorTema() {
  const { tema, alternar } = useTema()
  const aOscuro = tema === 'claro'
  const texto = aOscuro ? 'Tema oscuro' : 'Tema claro'
  return (
    <SidebarMenuButton
      onClick={alternar}
      tooltip={texto}
      aria-label={aOscuro ? 'Cambiar a tema oscuro' : 'Cambiar a tema claro'}
    >
      {aOscuro ? <Moon aria-hidden="true" /> : <Sun aria-hidden="true" />}
      <span>{texto}</span>
    </SidebarMenuButton>
  )
}
