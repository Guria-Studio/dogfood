import { act, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { VistaVivo } from './VistaVivo'

class WsFalso {
  static todos: WsFalso[] = []
  onopen: (() => void) | null = null
  onmessage: ((m: { data: string }) => void) | null = null
  onclose: (() => void) | null = null
  constructor(public url: string) {
    WsFalso.todos.push(this)
  }
  close() {}
}

const ev = (tipo: string, extra = {}) =>
  JSON.stringify({ ejecucion_id: 'e1', tipo, n_paso: 1, persona: 'Ana', escenario: 'reservar', paso_contrato: 'p1', razonamiento: 'r', accion: 'click', resultado: null, ts: new Date().toISOString(), ...extra })

beforeEach(() => {
  WsFalso.todos = []
  vi.stubGlobal('WebSocket', WsFalso)
})
afterEach(() => vi.unstubAllGlobals())

describe('vista en vivo', () => {
  it('crea la tarjeta y actualiza el frame', async () => {
    render(<VistaVivo />)
    const ws = WsFalso.todos[0]
    expect(ws.url).toMatch(/\/ws$/)
    act(() => {
      ws.onopen?.()
      ws.onmessage?.({ data: ev('frame', { frame_jpeg_b64: 'AAA' }) })
    })
    expect(await screen.findAllByTestId('tarjeta')).toHaveLength(1)
    expect(screen.getByAltText('Pantalla de Ana')).toHaveAttribute('src', 'data:image/jpeg;base64,AAA')
    act(() => ws.onmessage?.({ data: ev('frame', { frame_jpeg_b64: 'BBB' }) }))
    expect(screen.getAllByTestId('tarjeta')).toHaveLength(1)
    expect(screen.getByAltText('Pantalla de Ana')).toHaveAttribute('src', 'data:image/jpeg;base64,BBB')
  })

  it('clic amplía y Esc cierra', async () => {
    render(<VistaVivo />)
    act(() => WsFalso.todos[0].onmessage?.({ data: ev('paso') }))
    await userEvent.click(await screen.findByTestId('tarjeta'))
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    await userEvent.keyboard('{Escape}')
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('sin conexión avisa y reintenta cada 5 s', () => {
    vi.useFakeTimers()
    render(<VistaVivo />)
    act(() => WsFalso.todos[0].onclose?.())
    expect(screen.getByText(/no hay una corrida con vista activa/i)).toBeInTheDocument()
    expect(screen.getByText('uv run dogfood run --target predicts --vista')).toBeInTheDocument()
    act(() => {
      vi.advanceTimersByTime(5000)
    })
    expect(WsFalso.todos).toHaveLength(2)
    vi.useRealTimers()
  })
})
