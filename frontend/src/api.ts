// Tom = samma adress som sidan (produktionsbygget). Lokalt körs backend separat på :8000.
export const API_URL =
  import.meta.env.VITE_API_URL ?? (import.meta.env.DEV ? 'http://localhost:8000' : '')

// http→ws, https→wss. Utan API_URL används sidans egen adress.
export const WS_URL = (API_URL || location.origin).replace(/^http/, 'ws') + '/ws'
