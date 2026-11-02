import { useSyncExternalStore } from 'react'

export type Tema = 'claro' | 'oscuro'
const CLAVE = 'dogfood.tema'
const EVENTO = 'dogfood:tema'

function leerTema(): Tema {
  const guardado = localStorage.getItem(CLAVE)
  // El claro cálido es el predeterminado; el oscuro solo si se eligió.
  return guardado === 'oscuro' ? 'oscuro' : 'claro'
}

function aplicar(tema: Tema) {
  document.documentElement.classList.toggle('dark', tema === 'oscuro')
}

/** Aplica el tema guardado; llamar al arrancar para evitar el parpadeo. */
export function aplicarTemaGuardado() {
  aplicar(leerTema())
}

/** Cambia al otro tema y avisa a todos los `useTema` (selector, paleta de comandos). */
export function alternarTema() {
  const nuevo: Tema = leerTema() === 'oscuro' ? 'claro' : 'oscuro'
  localStorage.setItem(CLAVE, nuevo)
  aplicar(nuevo)
  window.dispatchEvent(new Event(EVENTO))
}

function suscribir(aviso: () => void) {
  window.addEventListener(EVENTO, aviso)
  window.addEventListener('storage', aviso)
  return () => {
    window.removeEventListener(EVENTO, aviso)
    window.removeEventListener('storage', aviso)
  }
}

export function useTema() {
  const tema = useSyncExternalStore(suscribir, leerTema)
  return { tema, alternar: alternarTema }
}
