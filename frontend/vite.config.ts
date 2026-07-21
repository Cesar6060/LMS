import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  // loadEnv with an empty prefix includes process env vars, which is how
  // Cloudflare Pages (and CI) supply VITE_API_URL; import.meta.env does not
  // exist in this file.
  const env = loadEnv(mode, process.cwd(), '')

  // A production bundle silently built without VITE_API_URL would fall back
  // to localhost:8000 and ship a dead site. Fail the build loudly instead.
  if (mode === 'production' && !env.VITE_API_URL) {
    throw new Error(
      'VITE_API_URL must be set for production builds ' +
      '(e.g. https://stemquest-api.onrender.com/api — the /api suffix is required).'
    )
  }

  return {
    plugins: [react()],
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      port: 5173,
      host: true,
      watch: {
        // File events don't reliably propagate into the Docker bind mount on
        // macOS, which leaves Vite serving stale transforms until a restart.
        usePolling: true,
        interval: 300,
      },
    },
  }
})
