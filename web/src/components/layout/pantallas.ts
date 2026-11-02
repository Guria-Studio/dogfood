import {
  CalendarClock,
  ChartColumn,
  CircleHelp,
  ClipboardList,
  Eye,
  FolderGit2,
  FolderKanban,
  Compass,
  Workflow,
  History,
  House,
  Layers,
  ListChecks,
  type LucideIcon,
  Logs,
  Smartphone,
  SlidersHorizontal,
} from 'lucide-react'

/** Proyecto al que van las rutas viejas sin proyecto (`/recorridos`, `/corridas/$id`…). */
export const PROYECTO_POR_DEFECTO = 'predicts'

// ponytail: lista fija hasta que F11.1.T2 traiga GET /api/proyectos; predicts es el único objetivo configurado.
export const PROYECTOS = [{ id: 'predicts', nombre: 'predicts', tipo: 'Web' }] as const

/** Barra global: pantallas fuera de un proyecto. */
export const GRUPOS = [
  {
    titulo: '',
    enlaces: [
      { to: '/', texto: 'Inicio', icono: House },
      { to: '/proyectos', texto: 'Proyectos', icono: FolderKanban },
    ],
  },
  {
    titulo: 'Automatización',
    enlaces: [
      { to: '/suites', texto: 'Suites', icono: Layers },
      { to: '/programaciones', texto: 'Programaciones', icono: CalendarClock },
    ],
  },
] as const

export const AYUDA = { to: '/ayuda', texto: 'Ayuda', icono: CircleHelp } as const

export interface SeccionProyecto {
  /** Segmento de la ruta debajo de `/proyectos/$proyecto/`. */
  seg: string
  texto: string
  icono: LucideIcon
  conteo?: 'casos' | 'corridas'
}

/** Barra de proyecto: secciones de `/proyectos/$proyecto/…`, por grupo. */
export const GRUPOS_PROYECTO: { titulo: string; secciones: SeccionProyecto[] }[] = [
  {
    titulo: 'Configuración',
    secciones: [
      { seg: 'fuentes', texto: 'Fuentes', icono: FolderGit2 },
      { seg: 'mapa', texto: 'Mapa', icono: Compass },
      { seg: 'github', texto: 'Acción de GitHub', icono: Workflow },
    ],
  },
  {
    titulo: 'Espacio de trabajo',
    secciones: [
      { seg: 'casos', texto: 'Casos de prueba', icono: ClipboardList, conteo: 'casos' },
      { seg: 'corridas', texto: 'Corridas', icono: History, conteo: 'corridas' },
      { seg: 'recorridos', texto: 'Recorridos', icono: ListChecks },
    ],
  },
  { titulo: 'Análisis', secciones: [{ seg: 'insights', texto: 'Insights', icono: ChartColumn }] },
  { titulo: 'Actividad', secciones: [{ seg: 'actividad', texto: 'Registro', icono: Logs }] },
  {
    titulo: 'Dispositivos',
    secciones: [
      { seg: 'dispositivos', texto: 'Dispositivos', icono: Smartphone },
      { seg: 'vista', texto: 'Vista en vivo', icono: Eye },
    ],
  },
  {
    titulo: 'Ajustes del proyecto',
    secciones: [
      { seg: 'ajustes/general', texto: 'General', icono: SlidersHorizontal },
      { seg: 'ajustes/entorno', texto: 'Entorno', icono: SlidersHorizontal },
      { seg: 'ajustes/comportamiento', texto: 'Comportamiento', icono: SlidersHorizontal },
      { seg: 'ajustes/notificaciones', texto: 'Notificaciones', icono: SlidersHorizontal },
    ],
  },
]

export const SECCIONES = GRUPOS_PROYECTO.flatMap((g) => g.secciones)

/** Para la paleta de comandos: pantallas globales y las del proyecto por defecto. */
export const PANTALLAS: { to: string; texto: string; icono: LucideIcon }[] = [
  ...GRUPOS.flatMap((g) => [...g.enlaces]),
  ...SECCIONES.map((s) => ({ to: `/proyectos/${PROYECTO_POR_DEFECTO}/${s.seg}`, texto: s.texto, icono: s.icono })),
  AYUDA,
]
