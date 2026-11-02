import { GRUPOS, SECCIONES } from './pantallas'

type Miga = { texto: string; to?: string }

const GLOBALES: Record<string, string> = Object.fromEntries(
  [...GRUPOS.flatMap((g) => [...g.enlaces]), { to: '/ayuda', texto: 'Ayuda' }].map((e) => [e.to.slice(1), e.texto]),
)

/** Ruta → migas. La última es la página actual. */
export function migasDe(ruta: string): Miga[] {
  const [, a = '', b, c, d] = ruta.split('/').map(decodeURIComponent)
  if (a === 'proyectos' && b) {
    const base = `/proyectos/${b}`
    const proyecto = { texto: b, to: base }
    if (!c) return [{ texto: 'Proyectos', to: '/proyectos' }, { texto: b }]
    if (c === 'corridas' && d)
      return [proyecto, { texto: 'Corridas', to: `${base}/corridas` }, { texto: `Corrida ${d}` }]
    if (c === 'ejecuciones' && d)
      return [proyecto, { texto: 'Corridas', to: `${base}/corridas` }, { texto: `Ejecución ${d}` }]
    if (c === 'diffs' && d) return [proyecto, { texto: 'Cambios entre versiones', to: `${base}/diffs` }, { texto: d }]
    if (c === 'ajustes') return [proyecto, { texto: 'Ajustes' }, { texto: SECCIONES.find((s) => s.seg === `ajustes/${d}`)?.texto ?? d }]
    const s = SECCIONES.find((s) => s.seg === c)
    return s ? [proyecto, { texto: s.texto }] : [proyecto, { texto: 'No encontrada' }]
  }
  if (a === 'ayuda' && b) return [{ texto: 'Ayuda', to: '/ayuda' }, { texto: b }]
  if (a === 'corridas' && c === 'reporte') return [{ texto: `Corrida ${b}`, to: `/corridas/${b}` }, { texto: 'Reporte' }]
  if (a === 'lanzamientos') return [{ texto: 'Inicio', to: '/' }, { texto: `Lanzamiento ${b}` }]
  return [{ texto: GLOBALES[a] ?? 'No encontrada' }]
}
