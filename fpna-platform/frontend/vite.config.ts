import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendPort = env.VITE_BACKEND_PORT || '8001'
  return {
    plugins: [react()],
    server: {
      port: 3000,
      proxy: {
        '/api': {
          target: env.VITE_PROXY_TARGET || `http://127.0.0.1:${backendPort}`,
          changeOrigin: true,
          secure: false,
          // Match LONG_RUNNING_REQUEST_TIMEOUT_MS in api.ts (budget initialize can run many minutes)
          timeout: 900000,
          proxyTimeout: 900000,
        },
      },
    },
  }
})