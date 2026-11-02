import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
import { afterEach } from 'vitest'

afterEach(cleanup)

// Con la máquina cargada (CI, varios worktrees) 1 s se queda corto para findBy*.
configure({ asyncUtilTimeout: 10000 })

// jsdom no trae ResizeObserver ni scrollIntoView (los usan cmdk y Recharts).
globalThis.ResizeObserver ??= class {
  observe() {}
  unobserve() {}
  disconnect() {}
}
Element.prototype.scrollIntoView ??= () => {}
