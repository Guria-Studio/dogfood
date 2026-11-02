import { createFileRoute } from '@tanstack/react-router'

import { EncabezadoPagina } from '@/components/layout/EncabezadoPagina'
import { Dispositivos } from '@/features/vivo/Dispositivos'

export const Route = createFileRoute('/proyectos/$proyecto/dispositivos')({
  component: () => (
    <>
      <EncabezadoPagina titulo="Dispositivos" subtitulo="Navegadores y celulares disponibles para correr casos." ayuda="dispositivos" />
      <Dispositivos />
    </>
  ),
})
