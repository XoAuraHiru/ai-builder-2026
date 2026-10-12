export type RuntimeConfig = {
  apiUrl: string;
  authMode: "dev" | "firebase";
  firebase: { apiKey: string; authDomain: string; projectId: string; appId: string };
};

let cached: RuntimeConfig | null = null;

export async function getConfig(): Promise<RuntimeConfig> {
  if (cached) return cached;
  const res = await fetch("/api/config", { cache: "no-store" });
  cached = (await res.json()) as RuntimeConfig;
  return cached;
}
