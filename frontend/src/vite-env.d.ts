/// <reference types="vite/client" />

interface ImportMetaEnv {
  // The OAuth client ID from Google Cloud, used by the sign-in button
  readonly VITE_GOOGLE_CLIENT_ID?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
