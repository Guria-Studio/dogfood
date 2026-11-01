import { useSyncExternalStore } from "react"

const MOBILE_BREAKPOINT = 768
const CONSULTA = `(max-width: ${MOBILE_BREAKPOINT - 1}px)`

function suscribir(aviso: () => void) {
  const mql = window.matchMedia?.(CONSULTA)
  mql?.addEventListener("change", aviso)
  return () => mql?.removeEventListener("change", aviso)
}

export function useIsMobile() {
  return useSyncExternalStore(suscribir, () => window.innerWidth < MOBILE_BREAKPOINT)
}
