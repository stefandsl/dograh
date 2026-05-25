/** Client helpers for Telegram SIP Gateway API (until OpenAPI client is regenerated). */

const BASE = "/api/v1/organizations/telegram-sip-gateway";

export type GatewayProviderType = "sip_tg" | "tg2sip" | "custom";

export interface TelegramSipCredentials {
  sip_host: string;
  sip_port: number;
  sip_username: string;
  sip_password: string;
  sip_caller_id: string;
  telegram_destination_id: string;
  webhook_callback_url?: string | null;
  gateway_api_base_url?: string | null;
  gateway_api_key?: string | null;
}

export interface TelegramSipConfigListItem {
  id: number;
  name: string;
  gateway_provider_type: string;
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface TelegramSipConfigDetail extends TelegramSipConfigListItem {
  credentials: TelegramSipCredentials;
}

export interface TelegramSipCallLog {
  id: number;
  configuration_id: number;
  gateway_call_id?: string | null;
  direction: string;
  destination: string;
  status: string;
  error_code?: string | null;
  error_message?: string | null;
  events: Record<string, unknown>[];
  created_at: string;
  updated_at: string;
}

async function request<T>(
  path: string,
  token: string,
  init?: RequestInit,
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
      ...(init?.headers ?? {}),
    },
  });
  if (!res.ok) {
    let message = res.statusText;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (body.detail?.message) message = body.detail.message;
    } catch {
      /* ignore */
    }
    throw new Error(message);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export async function listTelegramSipConfigs(token: string) {
  return request<{ configurations: TelegramSipConfigListItem[] }>(
    "/configs",
    token,
  );
}

export async function getTelegramSipConfig(token: string, configId: number) {
  return request<TelegramSipConfigDetail>(`/configs/${configId}`, token);
}

export async function createTelegramSipConfig(
  token: string,
  body: {
    name: string;
    gateway_provider_type: GatewayProviderType;
    credentials: TelegramSipCredentials;
    is_enabled?: boolean;
  },
) {
  return request<TelegramSipConfigDetail>("/configs", token, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updateTelegramSipConfig(
  token: string,
  configId: number,
  body: {
    name?: string;
    gateway_provider_type?: GatewayProviderType;
    credentials?: TelegramSipCredentials;
    is_enabled?: boolean;
  },
) {
  return request<TelegramSipConfigDetail>(`/configs/${configId}`, token, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export async function deleteTelegramSipConfig(token: string, configId: number) {
  return request<{ ok: boolean }>(`/configs/${configId}`, token, {
    method: "DELETE",
  });
}

export async function testTelegramSipConfig(token: string, configId: number) {
  return request<{ ok: boolean; message: string; latency_ms?: number }>(
    `/configs/${configId}/test`,
    token,
    { method: "POST" },
  );
}

export async function initiateTelegramSipCall(
  token: string,
  configId: number,
  destination: string,
) {
  return request<TelegramSipCallLog>(`/configs/${configId}/calls`, token, {
    method: "POST",
    body: JSON.stringify({ destination }),
  });
}

export async function listTelegramSipCalls(token: string, configId: number) {
  return request<{ call_logs: TelegramSipCallLog[] }>(
    `/configs/${configId}/calls`,
    token,
  );
}
