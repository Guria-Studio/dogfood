import { EncabezadoPagina } from './EncabezadoPagina'
import { type Ilustracion, Vacio } from './Vacio'

/** Pantalla que todavía no tiene datos: encabezado y estado vacío ilustrado (nada de datos falsos). */
export function PaginaPendiente(props: {
  titulo: string
  subtitulo: string
  ilustracion: Ilustracion
  vacio: string
  texto: string
}) {
  return (
    <>
      <EncabezadoPagina titulo={props.titulo} subtitulo={props.subtitulo} />
      <Vacio ilustracion={props.ilustracion} titulo={props.vacio} texto={props.texto} />
    </>
  )
}
