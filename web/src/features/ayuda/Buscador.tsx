import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'
import { useEffect, useState } from 'react'

import { Card } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { buscarDocs, norm } from './api'

function Resaltado({ texto, q }: { texto: string; q: string }) {
  const i = norm(texto).indexOf(norm(q.trim()))
  if (i < 0 || !q.trim()) return <>{texto}</>
  const f = i + q.trim().length
  return (
    <>
      {texto.slice(0, i)}
      <mark className="rounded bg-yellow-200 px-0.5 text-foreground dark:bg-yellow-500/40">{texto.slice(i, f)}</mark>
      {texto.slice(f)}
    </>
  )
}

export function Buscador() {
  const [texto, setTexto] = useState('')
  const [q, setQ] = useState('')
  useEffect(() => {
    const t = setTimeout(() => setQ(texto.trim()), 250)
    return () => clearTimeout(t)
  }, [texto])
  const { data, isFetching } = useQuery({
    queryKey: ['ayuda', 'buscar', q],
    queryFn: () => buscarDocs(q),
    enabled: q.length >= 2,
  })
  return (
    <section className="space-y-3">
      <Input
        type="search"
        aria-label="Buscar en la ayuda"
        placeholder="Buscar en la ayuda…"
        value={texto}
        onChange={(e) => setTexto(e.target.value)}
      />
      {q.length >= 2 && data && (
        <ul className="space-y-2">
          {data.length === 0 && !isFetching && <li className="text-sm text-muted-foreground">Sin resultados para «{q}».</li>}
          {data.map((r) => (
            <li key={r.slug}>
              <Card className="p-3">
                <Link to="/ayuda/$slug" params={{ slug: r.slug }} className="font-medium hover:underline">
                  {r.titulo}
                </Link>
                <p className="text-sm text-muted-foreground">
                  <Resaltado texto={r.fragmento} q={q} />
                </p>
              </Card>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
