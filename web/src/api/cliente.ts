import createClient from 'openapi-fetch'

import type { paths } from './schema'

/** Cliente tipado de la API JSON del panel (mismo origen: `/api/*`). `schema.ts` se genera
 * con `npm run gen:api` desde el OpenAPI de FastAPI. */
export const cliente = createClient<paths>({
  // Absoluto: `new Request('/api/..')` falla sin origen (jsdom/Node); en el navegador es el mismo origen.
  baseUrl: globalThis.location?.origin ?? '',
  // Indirección para que los tests puedan reemplazar `globalThis.fetch` después de importar.
  fetch: (...args: Parameters<typeof fetch>) => globalThis.fetch(...args),
})
