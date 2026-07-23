import { StrictMode, useEffect } from 'react'
import { createRoot } from 'react-dom/client'
import {
  BrowserRouter,
  createRoutesFromChildren,
  matchRoutes,
  useLocation,
  useNavigationType,
} from 'react-router'
import * as Sentry from '@sentry/react'
import { AuthProvider } from './contexts/AuthContext'
import { ThemeProvider } from './contexts/ThemeContext'
import { ToastProvider } from './contexts/ToastContext'
import ErrorBoundary from './components/ErrorBoundary'
import App from './App'
import './index.css'

// Self-heal stale tabs after a deploy. Every deploy rotates the hashed
// lazy-chunk filenames; a tab opened under an older deploy then fails to
// import route chunks ("Failed to fetch dynamically imported module") and
// crashes into the ErrorBoundary. Vite fires vite:preloadError for exactly
// this case — reload once to pick up the fresh index.html. The timestamp
// guard prevents a reload loop if the network itself is broken.
window.addEventListener('vite:preloadError', (event) => {
  const lastReload = Number(sessionStorage.getItem('chunk-reload-at') ?? 0)
  if (Date.now() - lastReload > 30_000) {
    sessionStorage.setItem('chunk-reload-at', String(Date.now()))
    event.preventDefault()
    window.location.reload()
  }
})

// Initialize Sentry for error tracking
const sentryDsn = import.meta.env.VITE_SENTRY_DSN
if (sentryDsn) {
  Sentry.init({
    dsn: sentryDsn,
    integrations: [
      Sentry.reactRouterV7BrowserTracingIntegration({
        useEffect,
        useLocation,
        useNavigationType,
        createRoutesFromChildren,
        matchRoutes,
      }),
      // Default masking (maskAllText/blockAllMedia) stays on — student PII.
      Sentry.replayIntegration(),
    ],
    // Performance monitoring
    tracesSampleRate: import.meta.env.PROD ? 0.1 : 1.0,
    // Session replay for errors
    replaysSessionSampleRate: 0.1,
    replaysOnErrorSampleRate: 1.0,
    // Environment
    environment: import.meta.env.MODE,
  })
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary>
      <ThemeProvider>
        <BrowserRouter>
          <AuthProvider>
            <ToastProvider>
              <App />
            </ToastProvider>
          </AuthProvider>
        </BrowserRouter>
      </ThemeProvider>
    </ErrorBoundary>
  </StrictMode>,
)
