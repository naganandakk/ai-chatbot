import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

// LAN_HTTPS=1 serves the dev server over HTTPS on the local network so phones get a secure context (microphone, voice prompts).
// The certificate is made with mkcert; see the README. Without the flag the config is unchanged.
const lanHttps = process.env.LAN_HTTPS === "1";
const certDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "certs");
const certFile = path.join(certDir, "lan.pem");
const keyFile = path.join(certDir, "lan-key.pem");

if (lanHttps && (!fs.existsSync(certFile) || !fs.existsSync(keyFile))) {
  throw new Error(`LAN_HTTPS=1 needs ${certFile} and ${keyFile}. Create them with mkcert (see README).`);
}

// Limits what script, styles, and connections the page may use. Development needs inline
// scripts and eval for Vite's React refresh, so only the production build leaves them out.
// Google's sign-in script and button come from accounts.google.com; Google Fonts is loaded
// in index.html.
const contentSecurityPolicy = (development: boolean) =>
  [
    "default-src 'self'",
    `script-src 'self' https://accounts.google.com${development ? " 'unsafe-inline' 'unsafe-eval'" : ""}`,
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
    "font-src 'self' https://fonts.gstatic.com",
    "img-src 'self' data: blob: https:",
    "connect-src 'self' https://accounts.google.com",
    "frame-src https://accounts.google.com",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
  ].join("; ");

export default defineConfig(({ command }) => ({
  plugins: [
    react(),
    {
      // Production has no inline scripts, so the strict policy can be a meta tag. Hosts that
      // cannot set headers still get it this way.
      name: "content-security-policy-meta",
      apply: "build",
      transformIndexHtml: () => [
        {
          tag: "meta",
          attrs: { "http-equiv": "Content-Security-Policy", content: contentSecurityPolicy(false) },
          injectTo: "head-prepend",
        },
      ],
    },
  ],
  server: {
    headers: { "Content-Security-Policy": contentSecurityPolicy(command === "serve") },
    ...(lanHttps && {
      host: true,
      https: {
        cert: fs.readFileSync(certFile),
        key: fs.readFileSync(keyFile),
      },
    }),
    proxy: {
      "/api": {
        target: "http://127.0.0.1:5000",
        changeOrigin: true,
      },
    },
  },
  preview: {
    headers: { "Content-Security-Policy": contentSecurityPolicy(false) },
  },
}));
