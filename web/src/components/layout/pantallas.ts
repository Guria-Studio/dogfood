import { CircleHelp, ClipboardList, Eye, History, ListChecks, Smartphone } from 'lucide-react'

/** Pantallas del panel, por grupo (también las usa la paleta de comandos). */
export const GRUPOS = [
  {
    titulo: 'Corridas',
    enlaces: [
      { to: '/', texto: 'Corridas', icono: History },
      { to: '/casos', texto: 'Casos de prueba', icono: ClipboardList },
      { to: '/recorridos', texto: 'Recorridos', icono: ListChecks },
    ],
  },
  {
    titulo: 'Dispositivos',
    enlaces: [
      { to: '/dispositivos', texto: 'Dispositivos', icono: Smartphone },
      { to: '/vista', texto: 'Vista en vivo', icono: Eye },
    ],
  },
  { titulo: 'Ayuda', enlaces: [{ to: '/ayuda', texto: 'Ayuda', icono: CircleHelp }] },
] as const

export const PANTALLAS = GRUPOS.flatMap((g) => [...g.enlaces])
