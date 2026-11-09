import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';
import type { Connect, Plugin } from 'vite';

import { STUDIO_BASENAME } from './src/base.ts';
import en from './src/i18n/en.json' with { type: 'json' };

// The dev realm registers the OIDC callback and the post-logout page on
// 127.0.0.1:58000 (docs/architecture/role-applications.md). The dev and preview
// servers take that address and forward the API paths, so the browser sees one
// origin and the session cookie stays same-site (D8).
const API_URL = process.env.ALM_STUDIO_API_URL ?? 'http://127.0.0.1:58001';
const proxy = { '/auth': API_URL, '/health': API_URL };

/** The page title comes from the English catalogue, like every other visible string. */
function catalogueTitle(): Plugin {
  return {
    name: 'alm-catalogue-title',
    transformIndexHtml: { order: 'pre', handler: (html) => html.replace('__ALM_STUDIO_TITLE__', en.app.title) },
  };
}

/** `/` (the post-logout page) opens the studio. */
function rootToStudio(): Plugin {
  const redirect: Connect.NextHandleFunction = (request, response, next) => {
    if (request.url !== '/') return next();
    response.statusCode = 302;
    response.setHeader('Location', STUDIO_BASENAME);
    response.end();
  };
  return {
    name: 'alm-root-to-studio',
    configureServer: (server) => void server.middlewares.use(redirect),
    configurePreviewServer: (server) => void server.middlewares.use(redirect),
  };
}

export default defineConfig({
  base: STUDIO_BASENAME,
  plugins: [react(), catalogueTitle(), rootToStudio()],
  server: { host: '127.0.0.1', port: 58000, strictPort: true, proxy },
  preview: { host: '127.0.0.1', port: 58000, strictPort: true, proxy },
  build: { outDir: 'dist', sourcemap: true },
});
