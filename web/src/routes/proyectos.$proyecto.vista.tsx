import { createFileRoute } from '@tanstack/react-router'

import { EncabezadoPagina } from '@/components/layout/EncabezadoPagina'
import { VistaVivo } from '@/features/vivo/VistaVivo'

export const Route = createFileRoute('/proyectos/$proyecto/vista')({
  component: () => (
    <>
      <EncabezadoPagina titulo="Vista en vivo" subtitulo="La pantalla de cada persona mientras corre." ayuda="vista" />
      <VistaVivo />
    </>
  ),
})
