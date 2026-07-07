export interface EngineOptions {
  headless?: boolean;
  browser_type?: string;
  user_data_dir?: string;
  viewport?: { width: number; height: number };
  headers?: Record<string, string>;
  cookies?: Record<string, string>;
  proxies?: Record<string, string>;
  delay: [number, number];
  timeout: number;
  retry_times: number;
  backoff_factor: number;
}

export interface FormatOptions {
  enabled: boolean;
}

export interface TxtOptions extends FormatOptions {
  encoding: string;
}

export interface EpubOptions extends FormatOptions {
  compression: string;
  compresslevel: number;
  optimize_images: boolean;
  jpeg_quality: number;
  max_image_width: number;
  include_toc: boolean;
}

export interface ImgOptions extends FormatOptions {
  output_format: string;
}

export interface NotifyConfig {
  on_complete: boolean;
  on_incomplete: boolean;
  sound: "bell" | "system" | "none";
}

export interface PlatformConfig {
  browser: EngineOptions;
  requests: EngineOptions;
  api: EngineOptions;
  api_providers: string[];
}

export interface AppConfig {
  name: string;
  mode: string;
  max_workers: number;
  log_level: string;
  notify: NotifyConfig;
  platforms?: Record<string, PlatformConfig>;
  browser: EngineOptions;
  requests: EngineOptions;
  api: EngineOptions;
  txt: TxtOptions;
  epub: EpubOptions;
  img: ImgOptions;
  api_providers: Record<string, string[]>;
  groups: Record<string, Record<string, object>>;
}

const BASE = "http://localhost:8000";

export const configApi = {
  get: async (): Promise<AppConfig> => {
    const res = await fetch(`${BASE}/config`);
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  },
  save: async (data: Record<string, unknown>): Promise<void> => {
    const res = await fetch(`${BASE}/config`, {
      method: "PUT", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(res.statusText);
  },
};
