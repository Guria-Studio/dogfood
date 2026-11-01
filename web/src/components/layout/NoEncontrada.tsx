import { Link } from '@tanstack/react-router'
import { MapPinOff } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Vacio } from './Vacio'

/** 404 del SPA (`notFoundComponent` de la ruta raíz). */
export function NoEncontrada() {
  return (
    <Vacio
      icono={MapPinOff}
      titulo="Página no encontrada"
      texto="La dirección no corresponde a ninguna pantalla del panel."
      accion={
        <>
          <Button asChild>
            <Link to="/">Ir a corridas</Link>
          </Button>
          <Button asChild variant="outline">
            <Link to="/ayuda">Abrir la ayuda</Link>
          </Button>
        </>
      }
      className="mt-12"
    />
  )
}
