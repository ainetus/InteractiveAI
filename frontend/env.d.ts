/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API: string
  readonly VITE_DEFAULT_LOCALE: string
  readonly VITE_FALLBACK_LOCALE: string
  readonly VITE_POWERGRID_SIMU: string
  readonly VITE_RAILWAY_SIMU: string
  /** 'true' only for human-experiment builds: asks the simulator to start each session's scenario */
  readonly VITE_RAILWAY_SESSION_EVENTS?: string
  readonly VITE_ATM_SIMU: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
