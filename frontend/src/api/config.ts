export interface AppConfig {
  name: string;
  platform: string;
  mode: string;
  formats: string[];
  max_workers: number;
  groups: Record<string, Record<string, object>>;
}

const BASE = "http://localhost:8000";

export const configApi = {
  get: async (): Promise<AppConfig> => {
    const res = await fetch(`${BASE}/config`);
    if (!res.ok) throw new Error(res.statusText);
    return res.json();
  },
};
