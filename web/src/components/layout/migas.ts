type Miga = { texto: string; to?: string }

/** Ruta → migas. La última es la página actual. */
export function migasDe(ruta: string): Miga[] {
  const [, a = '', b] = ruta.split('/').map(decodeURIComponent)
  const corridas = { texto: 'Corridas', to: '/' }
  switch (a) {
    case '':
      return [{ texto: 'Corridas' }]
    case 'corridas':
      return [corridas, { texto: `Corrida ${b}` }]
    case 'ejecuciones':
      return [corridas, { texto: `Ejecución ${b}` }]
    case 'casos':
      return [corridas, { texto: 'Casos de prueba' }]
    case 'recorridos':
      return [corridas, { texto: 'Recorridos' }]
    case 'dispositivos':
      return [{ texto: 'Dispositivos' }]
    case 'vista':
      return [{ texto: 'Dispositivos', to: '/dispositivos' }, { texto: 'Vista en vivo' }]
    case 'ayuda':
      return b ? [{ texto: 'Ayuda', to: '/ayuda' }, { texto: b }] : [{ texto: 'Ayuda' }]
    default:
      return [{ texto: 'No encontrada' }]
  }
}
