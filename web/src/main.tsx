import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { AppProviders } from './app/AppProviders'
import { AppRoutes } from './app/AppRoutes'
import { apiUrl } from './shared/api'
import { webEnv } from './shared/env'
import '@fontsource-variable/inter/wght.css'
import './styles/index.css'
import './styles/behavioral.css'
import './styles/targeting.css'

if (webEnv.useMocks) {
  const { worker } = await import('./mocks/browser')
  await worker.start({
    onUnhandledRequest(request, print) {
      if (request.url.startsWith(`${apiUrl}/`)) print.error()
    },
  })
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppProviders>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AppProviders>
  </StrictMode>,
)
