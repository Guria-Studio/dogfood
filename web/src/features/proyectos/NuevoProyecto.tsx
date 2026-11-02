import { useQueryClient } from '@tanstack/react-query'
import { useNavigate } from '@tanstack/react-router'
import { Check, Terminal } from 'lucide-react'
import { useState } from 'react'

import { EncabezadoPagina } from '@/components/layout/EncabezadoPagina'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { crearProyecto } from './api'

const PASOS = ['Básico', 'Acceso', 'Contexto extra'] as const
const TIPOS = [['web', 'Web'], ['android', 'Android'], ['ios', 'iOS']] as const
type Modo = 'registro' | 'usuario' | 'ninguno'

export const slugDe = (s: string) =>
  s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '').replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 40)

export function urlValida(s: string) {
  try {
    const u = new URL(s.trim())
    return (u.protocol === 'http:' || u.protocol === 'https:') && u.hostname !== ''
  } catch {
    return false
  }
}

export function NuevoProyecto() {
  const navegar = useNavigate()
  const qc = useQueryClient()
  const [paso, setPaso] = useState(0)
  const [tipo, setTipo] = useState<(typeof TIPOS)[number][0]>('web')
  const [url, setUrl] = useState('')
  const [nombre, setNombre] = useState('')
  const [modo, setModo] = useState<Modo>('registro')
  const [usuario, setUsuario] = useState('')
  const [clave, setClave] = useState('')
  const [claveGuardada, setClaveGuardada] = useState(false)
  const [prd, setPrd] = useState('')
  const [instrucciones, setInstrucciones] = useState('')
  const [repo, setRepo] = useState('')
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  // Web: URL http(s); móvil: el objetivo (paquete o bundle id) no puede ir vacío.
  const objetivoOk = tipo === 'web' ? urlValida(url) : url.trim() !== ''
  const basicoOk = objetivoOk && nombre.trim() !== '' && slugDe(nombre) !== ''
  const slug = slugDe(nombre)

  async function subirPrd(f: File | undefined) {
    if (f) setPrd(await f.text())
  }

  async function terminar() {
    setEnviando(true)
    setError('')
    try {
      await crearProyecto({
        slug,
        nombre: nombre.trim(),
        tipo,
        objetivo: slug,
        url: url.trim(),
        acceso: modo === 'usuario' ? { usuario, secreto_ref: claveGuardada ? `${slug.toUpperCase().replace(/-/g, '_')}_PASSWORD` : '' } : {},
        instrucciones,
        repo_codigo: repo.trim(),
        prd,
        origen: 'Panel',
      })
      await qc.invalidateQueries({ queryKey: ['proyectos'] })
      await navegar({ to: '/proyectos/$proyecto/casos', params: { proyecto: slug } })
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
      setEnviando(false)
    }
  }

  return (
    <>
      <EncabezadoPagina titulo="Proyecto nuevo" subtitulo="Tres pasos y dogfood empieza a probar tu app." />
      <div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
        <Card>
          <CardHeader>
            <ol className="flex gap-4 text-sm" aria-label="Pasos">
              {PASOS.map((p, i) => (
                <li key={p} aria-current={i === paso ? 'step' : undefined} className={i === paso ? 'font-medium' : 'text-muted-foreground'}>
                  {i < paso ? <Check aria-hidden="true" className="mr-1 inline size-4" /> : `${i + 1}. `}
                  {p}
                </li>
              ))}
            </ol>
            <CardTitle>{PASOS[paso]}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {paso === 0 && (
              <>
                <fieldset className="flex gap-4">
                  <legend className="mb-1 text-sm font-medium">Tipo</legend>
                  {TIPOS.map(([v, t]) => (
                    <label key={v} className="flex items-center gap-1">
                      <input type="radio" name="tipo" checked={tipo === v} onChange={() => setTipo(v)} />
                      {t}
                    </label>
                  ))}
                </fieldset>
                <label className="block text-sm font-medium">
                  {tipo === 'web' ? 'URL' : 'Objetivo (paquete o bundle id)'}
                  <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder={tipo === 'web' ? 'https://mi-app.com' : 'com.empresa.app'} />
                </label>
                {url !== '' && !objetivoOk && (
                  <p role="alert" className="text-sm text-danger">
                    {tipo === 'web' ? 'Escribe una URL válida, con http:// o https://.' : 'Escribe el objetivo.'}
                  </p>
                )}
                <label className="block text-sm font-medium">
                  Nombre
                  <Input value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Mi app" />
                </label>
              </>
            )}
            {paso === 1 && (
              <>
                <fieldset className="space-y-2">
                  <legend className="mb-1 text-sm font-medium">¿Cómo inicia sesión la persona?</legend>
                  {([['registro', 'Se registra sola (como predicts)'], ['usuario', 'Con un usuario de prueba'], ['ninguno', 'Sin login']] as const).map(([v, t]) => (
                    <label key={v} className="flex items-center gap-2">
                      <input type="radio" name="acceso" checked={modo === v} onChange={() => setModo(v)} />
                      {t}
                    </label>
                  ))}
                </fieldset>
                {modo === 'usuario' && (
                  <div className="space-y-3">
                    <label className="block text-sm font-medium">
                      Usuario
                      <Input value={usuario} onChange={(e) => setUsuario(e.target.value)} />
                    </label>
                    {claveGuardada ? (
                      <p className="flex items-center gap-2 text-sm">
                        <Check aria-hidden="true" className="size-4 text-success" />
                        Contraseña guardada como secreto
                        <Button variant="ghost" size="sm" onClick={() => setClaveGuardada(false)}>Cambiar</Button>
                      </p>
                    ) : (
                      <div className="flex items-end gap-2">
                        <label className="flex-1 text-sm font-medium">
                          Contraseña
                          <Input type="password" autoComplete="new-password" value={clave} onChange={(e) => setClave(e.target.value)} />
                        </label>
                        <Button
                          variant="outline"
                          disabled={clave === ''}
                          onClick={() => { setClaveGuardada(true); setClave('') }}
                        >
                          Guardar
                        </Button>
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
            {paso === 2 && (
              <>
                <label className="block text-sm font-medium">
                  PRD (sube un .md o pega el texto)
                  <Input type="file" accept=".md,text/markdown" onChange={(e) => subirPrd(e.target.files?.[0])} />
                </label>
                <textarea aria-label="Texto del PRD" className="min-h-24 w-full rounded-md border bg-background p-2 text-sm" value={prd} onChange={(e) => setPrd(e.target.value)} />
                <label className="block text-sm font-medium">
                  Instrucciones extra
                  <textarea className="mt-1 min-h-20 w-full rounded-md border bg-background p-2 text-sm" value={instrucciones} onChange={(e) => setInstrucciones(e.target.value)} placeholder="Enfócate en el checkout; evita acciones destructivas" />
                </label>
                <label className="block text-sm font-medium">
                  Repo del código
                  <Input value={repo} onChange={(e) => setRepo(e.target.value)} placeholder="dueño/repo" />
                </label>
              </>
            )}
            {error && <p role="alert" className="text-sm text-danger">{error}</p>}
            <div className="flex justify-between pt-2">
              <Button variant="ghost" disabled={paso === 0 || enviando} onClick={() => setPaso(paso - 1)}>Atrás</Button>
              {paso < 2 ? (
                <Button disabled={paso === 0 && !basicoOk} onClick={() => setPaso(paso + 1)}>Siguiente</Button>
              ) : (
                <Button disabled={enviando} onClick={terminar}>Crear proyecto</Button>
              )}
            </div>
          </CardContent>
        </Card>
        <Card className="h-fit">
          <CardHeader><CardTitle>Otras formas de empezar</CardTitle></CardHeader>
          <CardContent className="space-y-3 text-sm">
            <p className="flex items-center gap-2"><Terminal aria-hidden="true" className="size-4" />Con la CLI:</p>
            <code className="block rounded-md bg-muted p-2">dogfood run --target mi-app</code>
            <p>Pedíselo a Papurri en Slack.</p>
          </CardContent>
        </Card>
      </div>
    </>
  )
}
