import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const backendTarget = (env.VITE_API_BASE_URL || 'http://localhost:8000')
    .replace(/\/health\/?$/, '')
    .replace(/\/$/, '');
  const backendProxy = () => ({
    target: backendTarget,
    changeOrigin: true,
    secure: true,
    configure(proxy) {
      proxy.on('error', (error, request) => {
        console.error(`[api proxy] ${request.method} ${request.url} -> ${backendTarget}: ${error.message}`);
      });
    },
  });

  return {
    plugins: [react()],
    server: {
      proxy: {
        '/auth': backendProxy(),
        '/get-metrics': backendProxy(),
        '/get-logs': backendProxy(),
        '/simulate/logs': backendProxy(),
        '/error-info': backendProxy(),
        '/internal': backendProxy(),
        '/admin': backendProxy(),
      },
    },
  };
});
