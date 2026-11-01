import { useQuery } from '@tanstack/react-query'
import { Link } from '@tanstack/react-router'

import { Card } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { idDe, listarDocs, obtenerDoc, pasosDe, SECCIONES } from './api'
import { Buscador } from './Buscador'

function ListaDocs({ docs }: { docs: { slug: string; titulo: string }[] }) {
  return (
    <ul className="space-y-1">
      {docs.map((d) => (
        <li key={d.slug}>
          <Link to="/ayuda/$slug" params={{ slug: d.slug }} className="text-primary hover:underline">
            {d.titulo}
          </Link>
        </li>
      ))}
    </ul>
  )
}

export function Portada({ pantalla }: { pantalla?: string }) {
  const todos = useQuery({ queryKey: ['ayuda', 'lista'], queryFn: () => listarDocs() })
  const deEsta = useQuery({
    queryKey: ['ayuda', 'lista', pantalla],
    queryFn: () => listarDocs(pantalla),
    enabled: !!pantalla,
  })
  const funciona = useQuery({ queryKey: ['ayuda', 'doc', 'como-funciona'], queryFn: () => obtenerDoc('como-funciona') })
  const pasos = pasosDe(funciona.data?.markdown ?? '')

  return (
    <div className="space-y-8">
      <Buscador />
      {pantalla && deEsta.data && deEsta.data.length > 0 && (
        <section aria-label="Ayuda para esta pantalla" className="rounded-lg border bg-card p-4">
          <h2 className="mb-2 text-lg font-semibold">Ayuda para esta pantalla</h2>
          <ListaDocs docs={deEsta.data} />
        </section>
      )}
      <section className="space-y-3">
        <h2 className="text-lg font-semibold">Cómo funciona</h2>
        {funciona.isLoading ? (
          <Skeleton className="h-24 w-full" />
        ) : (
          <ol className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {pasos.map((p, i) => (
              <li key={p.titulo}>
                <Link to="/ayuda/$slug" params={{ slug: 'como-funciona' }} hash={idDe(`Paso ${i + 1}. ${p.titulo}`)} className="block h-full">
                  <Card className="h-full p-4 hover:border-primary">
                    <span className="mb-1 flex size-7 items-center justify-center rounded-full bg-primary text-sm font-semibold text-primary-foreground">
                      {i + 1}
                    </span>
                    <h3 className="font-medium">{p.titulo}</h3>
                    <p className="text-sm text-muted-foreground">{p.linea}</p>
                  </Card>
                </Link>
              </li>
            ))}
          </ol>
        )}
      </section>
      <section className="grid gap-6 sm:grid-cols-3">
        {SECCIONES.map(([clave, nombre]) => (
          <div key={clave}>
            <h2 className="mb-2 text-lg font-semibold">{nombre}</h2>
            {todos.isLoading ? <Skeleton className="h-16 w-full" /> : <ListaDocs docs={(todos.data ?? []).filter((d) => d.seccion === clave)} />}
          </div>
        ))}
      </section>
    </div>
  )
}
