import { defineConfig, loadEnv } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite'


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
    plugins: [react(), tailwindcss(),],
    server: {
      proxy: {
        // The dev server also serves the SPA, so every backend path is
        // namespaced under /api and rewritten before it is forwarded. Without
        // this, API prefixes collide with frontend routes (/admin, /sites,
        // /tickets) and newer endpoints simply have no proxy at all.
        '/api': {
          ...backendProxy(),
          rewrite: (path) => path.replace(/^\/api/, ''),
        },
      },
    },
  };
});
