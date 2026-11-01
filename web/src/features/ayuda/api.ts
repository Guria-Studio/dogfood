export interface DocAyuda {
  slug: string
  titulo: string
  seccion: string
  orden: number
  pantallas: string[]
}
export interface DocCompleto {
  doc: DocAyuda
  markdown: string
}
export interface Resultado {
  slug: string
  titulo: string
  fragmento: string
  puntaje: number
}

async function pedir<T>(url: string): Promise<T> {
  const r = await globalThis.fetch(url)
  if (!r.ok) throw new Error(`${url}: ${r.status}`)
  return (await r.json()) as T
}

export const listarDocs = (pantalla?: string) =>
  pedir<DocAyuda[]>(pantalla ? `/api/ayuda?pantalla=${encodeURIComponent(pantalla)}` : '/api/ayuda')
export const buscarDocs = (q: string) => pedir<Resultado[]>(`/api/ayuda/buscar?q=${encodeURIComponent(q)}`)
export const obtenerDoc = (slug: string) => pedir<DocCompleto>(`/api/ayuda/${encodeURIComponent(slug)}`)

export const SECCIONES: [string, string][] = [
  ['empezar', 'Empezar'],
  ['guias', 'Guías'],
  ['referencia', 'Referencia'],
]

/** Pasos de «Cómo funciona»: cada `## Paso N. Título` con la primera frase de su «Qué hace». */
export function pasosDe(markdown: string): { titulo: string; linea: string }[] {
  return markdown
    .split(/^## /m)
    .slice(1)
    .filter((s) => /^Paso \d+/.test(s))
    .map((s) => {
      const [cabecera, ...resto] = s.split('\n')
      const hace = /\*\*Qué hace:\*\*\s*(.+)/.exec(resto.join('\n'))?.[1] ?? ''
      return {
        titulo: cabecera.replace(/^Paso \d+\.\s*/, '').trim(),
        linea: hace.split(/(?<=\.)\s/)[0].replace(/[*`]/g, ''),
      }
    })
}

/** Sin acentos ni mayúsculas, misma longitud (para resaltar). */
export const norm = (t: string) =>
  [...t.toLowerCase()].map((c) => (c.normalize('NFD').length === 1 ? c : c.normalize('NFD')[0])).join('')

export const idDe = (t: string) =>
  t
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-|-$/g, '')

/** Los `##` del Markdown (fuera de bloques de código). */
export function encabezados(md: string): { id: string; texto: string }[] {
  let dentro = false
  const salida: { id: string; texto: string }[] = []
  for (const l of md.split('\n')) {
    if (/^\s*(```|~~~)/.test(l)) dentro = !dentro
    const m = !dentro && /^## (.+)$/.exec(l)
    if (m) {
      const texto = m[1].replace(/[*`]/g, '').trim()
      salida.push({ id: idDe(texto), texto })
    }
  }
  return salida
}

/** `glosario.md`, `./x.md#a` o `../ops/y.md` → slug de la ayuda (o null si no es un .md relativo). */
export function slugDeLink(href?: string): { slug: string; hash?: string } | null {
  const m = href && /^(?!\w+:|\/)(?:[^#?]*\/)?([^/#?]+)\.md(#.*)?$/.exec(href)
  if (!m) return null
  const ops = /(^|\/)ops\/[^/]+\.md/.test(href)
  return { slug: (ops ? 'ops-' : '') + m[1], hash: m[2]?.slice(1) }
}
