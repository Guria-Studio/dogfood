import { useQuery } from '@tanstack/react-query'
import { Smartphone, TriangleAlert } from 'lucide-react'

import { Vacio } from '@/components/layout/Vacio'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
interface Dispositivo {
  id: string
  nombre: string
  plataforma: string
  estado: string
  permitido: boolean
  motivo: string
}

export function Dispositivos() {
  const { data, isPending, isError } = useQuery({
    queryKey: ['dispositivos'],
    queryFn: async (): Promise<Dispositivo[]> => {
      const r = await fetch('/api/dispositivos')
      if (!r.ok) throw new Error(String(r.status))
      return r.json()
    },
  })
  if (isPending) return <p className="text-muted-foreground">Cargando…</p>
  if (isError)
    return <Vacio error icono={TriangleAlert} titulo="No se pudo cargar la lista de dispositivos" texto="Revisa que el panel esté corriendo y vuelve a intentar." />
  if (!data.length)
    return (
      <Vacio
        icono={Smartphone}
        titulo="No hay dispositivos"
        texto={
          <>
            Conecta un Android (<code>docs/ops/android.md</code>) o configura un nodo iOS (
            <code>docs/ops/ios-nodo-mac.md</code>).
          </>
        }
      />
    )
  return (
    <div className="grid grid-cols-[repeat(auto-fill,minmax(300px,1fr))] gap-4">
      {data.map((d) => (
        <Card key={d.id}>
          <CardHeader>
            <CardTitle>{d.nombre}</CardTitle>
            <p className="text-muted-foreground text-sm">
              {d.plataforma} · {d.estado}
            </p>
          </CardHeader>
          <CardContent>
            {d.permitido ? (
              <img src={`/dispositivos/${d.id}/mjpeg`} alt={`Pantalla de ${d.nombre}`} className="max-w-full" />
            ) : (
              <p aria-disabled="true" className="text-destructive text-sm">
                Deshabilitado: {d.motivo}
              </p>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  )
}
