import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { Check, Copy, FileX } from 'lucide-react'
import { Children, isValidElement, type ReactNode, useState } from 'react'
import ReactMarkdown, { type Components } from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { Vacio } from '@/components/layout/Vacio'
import { Button } from '@/components/ui/button'
import { encabezados, idDe, listarDocs, obtenerDoc, slugDeLink } from './api'

function textoDe(n: ReactNode): string {
  if (typeof n === 'string' || typeof n === 'number') return String(n)
  if (Array.isArray(n)) return n.map(textoDe).join('')
  if (isValidElement<{ children?: ReactNode }>(n)) return textoDe(n.props.children)
  return ''
}

function Bloque({ children }: { children?: ReactNode }) {
  const [copiado, setCopiado] = useState(false)
  const copiar = () => {
    void navigator.clipboard?.writeText(textoDe(children).replace(/\n$/, ''))
    setCopiado(true)
    setTimeout(() => setCopiado(false), 1500)
  }
  return (
    <div className="relative">
      <Button
        type="button"
        variant="ghost"
        size="icon"
        aria-label="Copiar código"
        onClick={copiar}
        className="absolute right-2 top-2 size-7 text-muted-foreground"
      >
        {copiado ? <Check className="size-4" /> : <Copy className="size-4" />}
      </Button>
      <pre>{children}</pre>
    </div>
  )
}

const componentes: Components = {
  pre: ({ children }) => <Bloque>{Children.toArray(children)}</Bloque>,
  h2: ({ children }) => <h2 id={idDe(textoDe(children))}>{children}</h2>,
  a: ({ href, children }) => {
    const l = slugDeLink(href)
    return l ? (
      <Link to="/ayuda/$slug" params={{ slug: l.slug }} hash={l.hash}>
        {children}
      </Link>
    ) : (
      <a href={href}>{children}</a>
    )
  },
}

export function Documento({ slug }: { slug: string }) {
  const { data, isLoading, isError } = useQuery({ queryKey: ['ayuda', 'doc', slug], queryFn: () => obtenerDoc(slug) })
  const lista = useQuery({ queryKey: ['ayuda', 'lista'], queryFn: () => listarDocs() })
  if (isLoading) return <p className="text-muted-foreground">Cargando…</p>
  if (isError || !data)
    return <Vacio error icono={FileX} titulo={`No se encontró el documento «${slug}»`} accion={<Button asChild variant="outline"><Link to="/ayuda">Volver a la ayuda</Link></Button>} />

  const hermanos = (lista.data ?? []).filter((d) => d.seccion === data.doc.seccion)
  const i = hermanos.findIndex((d) => d.slug === slug)
  const anterior = i > 0 ? hermanos[i - 1] : undefined
  const siguiente = i >= 0 ? hermanos[i + 1] : undefined
  const toc = encabezados(data.markdown)

  return (
    <div className="flex gap-8">
      <article className="min-w-0 flex-1">
        <div className="prose max-w-none dark:prose-invert">
          <ReactMarkdown remarkPlugins={[remarkGfm]} components={componentes}>
            {data.markdown}
          </ReactMarkdown>
        </div>
        <nav aria-label="Anterior y siguiente" className="mt-10 flex justify-between border-t pt-4 text-sm">
          {anterior ? (
            <Link to="/ayuda/$slug" params={{ slug: anterior.slug }}>
              ← {anterior.titulo}
            </Link>
          ) : (
            <span />
          )}
          {siguiente && (
            <Link to="/ayuda/$slug" params={{ slug: siguiente.slug }}>
              {siguiente.titulo} →
            </Link>
          )}
        </nav>
      </article>
      {toc.length > 0 && (
        <aside aria-label="En esta página" className="sticky top-4 hidden h-fit w-56 shrink-0 text-sm lg:block">
          <p className="mb-2 font-semibold">En esta página</p>
          <ul className="space-y-1">
            {toc.map((h) => (
              <li key={h.id}>
                <a href={`#${h.id}`} className="text-muted-foreground hover:text-foreground">
                  {h.texto}
                </a>
              </li>
            ))}
          </ul>
        </aside>
      )}
    </div>
  )
}
