import { useCallback, useState } from 'react'

export type Tema = 'claro' | 'oscuro'
const CLAVE = 'dogfood.tema'

function leerTema(): Tema {
  const guardado = localStorage.getItem(CLAVE)
  if (guardado === 'claro' || guardado === 'oscuro') return guardado
  const oscuro = window.matchMedia?.('(prefers-color-scheme: dark)').matches
  return oscuro ? 'oscuro' : 'claro'
}

function aplicar(tema: Tema) {
  document.documentElement.classList.toggle('dark', tema === 'oscuro')
}

/** Aplica el tema guardado; llamar al arrancar para evitar el parpadeo. */
export function aplicarTemaGuardado() {
  aplicar(leerTema())
}

export function useTema() {
  const [tema, setTema] = useState<Tema>(leerTema)
  const alternar = useCallback(() => {
    const nuevo: Tema = tema === 'oscuro' ? 'claro' : 'oscuro'
    localStorage.setItem(CLAVE, nuevo)
    aplicar(nuevo)
    setTema(nuevo)
  }, [tema])
  return { tema, alternar }
}
