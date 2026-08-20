import { defineConfig, type Plugin } from "vite";
import react from "@vitejs/plugin-react";

// Ritarinn's backend. Bound to loopback; see backend/ritarinn/config.py.
const BACKEND = "http://127.0.0.1:8756";

/**
 * Content Security Policy.
 *
 * The application must work with the machine's internet connection switched
 * off, so the policy forbids every remote origin outright rather than listing
 * trusted ones. No CDN scripts, no remote fonts, no analytics: everything the
 * page loads is served from this origin.
 *
 * `style-src 'unsafe-inline'` is required because CodeMirror injects its
 * stylesheet as an inline <style> element at runtime. It does not widen the
 * network surface — inline styles cannot fetch anything.
 */
function contentSecurityPolicy(isDev: boolean): string {
  const directives = [
    "default-src 'none'",
    // Vite's dev server serves modules and an inline HMR bootstrap.
    isDev ? "script-src 'self' 'unsafe-inline'" : "script-src 'self'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self'",
    // Same-origin API calls go through the dev proxy below; the explicit
    // loopback entries cover running the built frontend against the backend
    // directly. `ws:` is the dev server's hot-reload channel only.
    isDev
      ? `connect-src 'self' ${BACKEND} http://localhost:8756 ws://127.0.0.1:5173 ws://localhost:5173`
      : `connect-src 'self' ${BACKEND} http://localhost:8756`,
    "base-uri 'none'",
    "form-action 'none'",
    // 'frame-ancestors' is deliberately absent: browsers ignore it when it
    // arrives in a <meta> element and log a console warning. A server hosting
    // a production build should send it as an HTTP header instead — the
    // backend already does so for its own responses.
  ];
  return directives.join("; ");
}

function cspPlugin(): Plugin {
  let isDev = false;
  return {
    name: "ritarinn-csp",
    configResolved(config) {
      isDev = config.command === "serve";
    },
    transformIndexHtml(html) {
      return html.replace(
        "<!--CSP-->",
        `<meta http-equiv="Content-Security-Policy" content="${contentSecurityPolicy(isDev)}" />`,
      );
    },
  };
}

export default defineConfig({
  plugins: [react(), cspPlugin()],
  server: {
    // Loopback only. Ritarinn is a single-user desktop application; exposing
    // the editor to the network is not a default anyone should get by accident.
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      // Proxying keeps the browser on one origin, so ordinary use makes no
      // cross-origin request at all.
      "/api": { target: BACKEND, changeOrigin: false },
    },
  },
  preview: { host: "127.0.0.1", port: 4173, strictPort: true },
  build: { outDir: "dist", sourcemap: true },
});
