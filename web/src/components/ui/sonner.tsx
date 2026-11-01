import { Toaster as Sonner, type ToasterProps } from 'sonner'

/** Avisos efímeros (`toast` de `sonner`); montar una vez en la raíz. */
export function Toaster(props: ToasterProps) {
  return <Sonner richColors closeButton {...props} />
}

export { toast } from 'sonner'
