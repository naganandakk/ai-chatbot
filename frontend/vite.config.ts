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

export default defineConfig({
  plugins: [react()],
  server: {
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
});
