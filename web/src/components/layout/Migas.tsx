import { Link, useLocation } from '@tanstack/react-router'
import { Fragment } from 'react'

import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'
import { migasDe } from './migas'

export function Migas() {
  const migas = migasDe(useLocation({ select: (l) => l.pathname }))
  return (
    <Breadcrumb aria-label="Ruta">
      <BreadcrumbList>
        {migas.map((m, i) => (
          <Fragment key={i}>
            {i > 0 && <BreadcrumbSeparator className="hidden md:block" />}
            <BreadcrumbItem className={i < migas.length - 1 ? 'hidden md:block' : undefined}>
              {m.to ? (
                <BreadcrumbLink asChild>
                  <Link to={m.to}>{m.texto}</Link>
                </BreadcrumbLink>
              ) : (
                <BreadcrumbPage>{m.texto}</BreadcrumbPage>
              )}
            </BreadcrumbItem>
          </Fragment>
        ))}
      </BreadcrumbList>
    </Breadcrumb>
  )
}
