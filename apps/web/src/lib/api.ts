import { getConfig } from "./config";
import { deviceId } from "./device";
import { detailMessage } from "./errors";
import { authHeaders } from "./session";

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

function deviceHeader(): Record<string, string> {
  const id = deviceId();
  return id ? { "X-Device-Id": id } : {};
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const cfg = await getConfig();
  const res = await fetch(`${cfg.apiUrl}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...deviceHeader(), ...(await authHeaders()), ...(init.headers ?? {}) },
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = detailMessage((await res.json()).detail, detail);
    } catch {}
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export type Me = {
  uid: string;
  email: string;
  full_name: string | null;
  roles: string[];
  person_id: string | null;
  accounts: { id: string; number: string }[];
};

export type Holding = {
  instrument: string;
  name: string;
  units: string;
  price: string;
  price_as_of: string;
  value: string;
  cost_basis: string;
  pnl: string;
  pnl_pct: string;
  kind: "fund" | "stock" | "etf" | "cash";
  risk_band: number | null;
};

export type Portfolio = {
  account_id: string;
  as_of: string;
  total_value: string;
  total_cost: string;
  pnl: string;
  pnl_pct: string;
  holdings: Holding[];
  by_fund: Record<string, string>;
  by_asset_class: Record<string, string>;
  by_region: Record<string, string>;
  by_instrument: Record<string, string>;
  cash: string;
};

export async function apiUpload<T>(path: string, form: FormData): Promise<T> {
  const cfg = await getConfig();
  const res = await fetch(`${cfg.apiUrl}${path}`, { method: "POST", body: form, headers: { ...deviceHeader(), ...(await authHeaders()) } });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = detailMessage((await res.json()).detail, detail);
    } catch {}
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}
