import { Moon, Sun } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { useTema } from './tema'

export function SelectorTema() {
  const { tema, alternar } = useTema()
  const aOscuro = tema === 'claro'
  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={alternar}
      aria-label={aOscuro ? 'Cambiar a tema oscuro' : 'Cambiar a tema claro'}
      className="justify-start"
    >
      {aOscuro ? <Moon aria-hidden="true" /> : <Sun aria-hidden="true" />}
      {aOscuro ? 'Tema oscuro' : 'Tema claro'}
    </Button>
  )
}
