/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Release version, set at build time by the Publish workflow (see deploy/nginx/Dockerfile). */
  readonly VITE_APP_VERSION?: string;
}
