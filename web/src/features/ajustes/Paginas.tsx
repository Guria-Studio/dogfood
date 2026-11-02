import { useNavigate } from '@tanstack/react-router'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'

import { borrarProyecto, type Entorno, probarSlack, useProyecto } from './api'
import { Ayuda, Campo, clase, Interruptor, PaginaAjustes, Tarjeta } from './comun'

const EJEMPLO = 'Enfócate en el checkout; prueba casos borde; evita acciones destructivas'
const TIPOS = { web: 'Web', flutter_web: 'Web (Flutter)', android: 'Android', ios: 'iOS' }

function ZonaPeligro({ slug, nombre }: { slug: string; nombre: string }) {
  const ir = useNavigate()
  const [texto, setTexto] = useState('')
  const [error, setError] = useState<string | null>(null)
  return (
    <Tarjeta peligro titulo="Zona de peligro" texto="Borrar el proyecto no se puede deshacer.">
      <Campo etiqueta={`Escribe «${nombre}» para confirmar`}>
        <Input value={texto} onChange={(e) => setTexto(e.target.value)} />
      </Campo>
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      <Button
        variant="destructive" disabled={texto !== nombre}
        onClick={() => borrarProyecto(slug).then(() => ir({ to: '/proyectos' }), (e: Error) => setError(e.message))}
      >
        Borrar proyecto
      </Button>
    </Tarjeta>
  )
}

export function General({ slug }: { slug: string }) {
  return (
    <PaginaAjustes
      slug={slug} titulo="General" subtitulo="Nombre, tipo e instrucciones del proyecto." campos={['nombre', 'instrucciones']}
      extra={<GeneralPeligro slug={slug} />}
    >
      {(v, cambiar, p) => (
        <>
          <Tarjeta titulo="Proyecto">
            <Campo etiqueta="Nombre">
              <Input value={v.nombre} onChange={(e) => cambiar({ nombre: e.target.value })} />
            </Campo>
            <Campo etiqueta="Tipo" ayuda="El tipo no se puede cambiar después de crear el proyecto.">
              <Input value={TIPOS[p.tipo]} disabled readOnly />
            </Campo>
          </Tarjeta>
          <Tarjeta titulo="Instrucciones extra" texto="Lo que el agente debe tener en cuenta en cada corrida.">
            <Campo etiqueta="Instrucciones" ayuda={`Ejemplo: ${EJEMPLO}`}>
              <textarea className={clase} rows={4} value={v.instrucciones} placeholder={EJEMPLO} onChange={(e) => cambiar({ instrucciones: e.target.value })} />
            </Campo>
          </Tarjeta>
        </>
      )}
    </PaginaAjustes>
  )
}
function GeneralPeligro({ slug }: { slug: string }) {
  const { data } = useProyecto(slug)
  return data ? <ZonaPeligro slug={slug} nombre={data.nombre} /> : null
}

const NUEVO: Entorno = { nombre: '', url: '', predeterminado: false }

export function EntornoPagina({ slug }: { slug: string }) {
  return (
    <PaginaAjustes slug={slug} titulo="Entorno" subtitulo="Dónde corre la app: URL y usuario de prueba." campos={['entornos']}>
      {(v, cambiar, p) => {
        const lista = v.entornos
        const poner = (i: number, c: Partial<Entorno>) => cambiar({ entornos: lista.map((e, j) => (j === i ? { ...e, ...c } : e)) })
        const predeterminado = (i: number) => cambiar({ entornos: lista.map((e, j) => ({ ...e, predeterminado: j === i })) })
        return (
          <Tarjeta titulo="Entornos" texto="Cada corrida usa el entorno predeterminado, salvo que elijas otro.">
            {lista.length === 0 && <Ayuda>Todavía no hay entornos.</Ayuda>}
            {lista.map((e, i) => (
              <div key={i} className="space-y-2 rounded-md border p-3">
                <Campo etiqueta={`Nombre del entorno ${i + 1}`}>
                  <Input value={e.nombre} onChange={(x) => poner(i, { nombre: x.target.value })} />
                </Campo>
                <Campo etiqueta={`URL del entorno ${i + 1}`}>
                  <Input value={e.url} onChange={(x) => poner(i, { url: x.target.value })} />
                </Campo>
                <p className="text-sm text-muted-foreground">{p.acceso.usuario || 'Sin cuenta de prueba'}</p>
                <div className="flex items-center gap-2">
                  {e.predeterminado ? <span className="text-sm font-medium">Predeterminado</span> : (
                    <Button variant="outline" size="sm" onClick={() => predeterminado(i)}>Marcar como predeterminado</Button>
                  )}
                  <Button variant="ghost" size="sm" onClick={() => cambiar({ entornos: lista.filter((_, j) => j !== i) })}>Quitar</Button>
                </div>
              </div>
            ))}
            <Button variant="outline" onClick={() => cambiar({ entornos: [...lista, { ...NUEVO, predeterminado: lista.length === 0 }] })}>
              Agregar entorno
            </Button>
          </Tarjeta>
        )
      }}
    </PaginaAjustes>
  )
}

export function Comportamiento({ slug }: { slug: string }) {
  return (
    <PaginaAjustes slug={slug} titulo="Comportamiento" subtitulo="Cómo se ejecuta cada corrida." campos={['comportamiento']}>
      {({ comportamiento: c }, cambiar) => {
        const poner = (x: Partial<typeof c>) => cambiar({ comportamiento: { ...c, ...x } })
        return (
          <>
            <Tarjeta titulo="Sesión">
              <Interruptor
                etiqueta="Iniciar sesión una vez por corrida" valor={c.login_una_vez} cambiar={(v) => poner({ login_una_vez: v })}
                ayuda="Reutiliza la sesión en todos los casos de la corrida en vez de iniciar sesión en cada uno."
              />
            </Tarjeta>
            <Tarjeta titulo="Pantalla y paralelismo">
              <Campo etiqueta="Viewport" ayuda="Tamaño de pantalla del navegador. El de escritorio es 1920×1080; el de celular simula un teléfono.">
                <select className={clase} value={c.viewport} onChange={(e) => poner({ viewport: e.target.value as typeof c.viewport })}>
                  <option value="escritorio">Escritorio (1920×1080)</option>
                  <option value="movil">Celular (390×844)</option>
                </select>
              </Campo>
              <Campo etiqueta="Casos al mismo tiempo" ayuda="Cuántos casos corren en paralelo. Vacío usa el valor de la configuración.">
                <Input
                  type="number" min={1} max={20} value={c.concurrencia ?? ''}
                  onChange={(e) => poner({ concurrencia: e.target.value ? Number(e.target.value) : null })}
                />
              </Campo>
            </Tarjeta>
          </>
        )
      }}
    </PaginaAjustes>
  )
}

export function Notificaciones({ slug }: { slug: string }) {
  const [webhook, setWebhook] = useState('')
  const [prueba, setPrueba] = useState<string | null>(null)
  return (
    <PaginaAjustes
      slug={slug} titulo="Notificaciones e issues" subtitulo="A quién avisar y dónde publicar lo que encuentra el agente."
      campos={['notificaciones']} secretos={{ slack_webhook: webhook }} limpiarSecretos={() => setWebhook('')}
    >
      {({ notificaciones: n }, cambiar) => {
        const poner = (x: Partial<typeof n>) => cambiar({ notificaciones: { ...n, ...x } })
        return (
          <>
            <Tarjeta titulo="Slack" texto="Un resumen al terminar cada corrida.">
              <Campo etiqueta="Webhook de Slack" ayuda={n.slack ? 'Hay un webhook guardado. Escribe uno nuevo para reemplazarlo.' : 'Se guarda como secreto y no se vuelve a mostrar.'}>
                <Input type="password" autoComplete="off" value={webhook} placeholder={n.slack ? '••••••••' : 'https://hooks.slack.com/…'} onChange={(e) => setWebhook(e.target.value)} />
              </Campo>
              <div className="flex items-center gap-3">
                <Button variant="outline" disabled={!n.slack} onClick={() => probarSlack(slug).then(() => setPrueba('Aviso enviado'), (e: Error) => setPrueba(e.message))}>
                  Probar
                </Button>
                {prueba && <span role="status" className="text-sm">{prueba}</span>}
              </div>
            </Tarjeta>
            <Tarjeta titulo="Issues de GitHub">
              <Interruptor etiqueta="Publicar issues" valor={n.issues_github} cambiar={(v) => poner({ issues_github: v })} ayuda="Abre un issue por cada hallazgo nuevo." />
              <Campo etiqueta="Repositorio" ayuda="dueño/repo">
                <Input value={n.repo} onChange={(e) => poner({ repo: e.target.value })} />
              </Campo>
              <Campo etiqueta="Etiqueta" ayuda="Se agrega a cada issue publicado.">
                <Input value={n.etiqueta} onChange={(e) => poner({ etiqueta: e.target.value })} />
              </Campo>
            </Tarjeta>
            <Tarjeta titulo="Linear o Jira"><Ayuda>Próximamente</Ayuda></Tarjeta>
          </>
        )
      }}
    </PaginaAjustes>
  )
}
