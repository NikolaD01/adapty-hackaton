export const webEnv = {
  apiBase: (import.meta.env.VITE_API_BASE || 'http://localhost:8000').replace(/\/+$/, ''),
  appId: import.meta.env.VITE_APP_ID || 'c6c7bdd1-1010-4343-8b29-837a77793cab',
  useMocks: import.meta.env.VITE_USE_MOCKS === undefined
    ? import.meta.env.DEV
    : import.meta.env.VITE_USE_MOCKS === 'true',
}
