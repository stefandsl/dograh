/**
 * IM channels API client.
 *
 * TODO(phase-4b-followup): the generated SDK at `@/client/sdk.gen` does
 * not yet include the `/api/v1/im/channels/*` routes (they ship in Phase
 * 4a). Run `npm run generate-client` against an api with the new routes
 * and replace the body of each function below with the typed SDK call.
 *
 * Until then, this module uses hand-rolled fetch — it mirrors the auth
 * pattern (`getAccessToken()` → `Authorization: Bearer <jwt>`) the
 * generated client uses via its interceptor.
 */

export interface TelegramChannel {
  id: number;
  type: 'telegram';
  name: string;
  enabled: boolean;
  api_key_id: number | null;
  config: {
    bot_token: string;          // masked to last 6 chars
    allowed_user_ids?: number[];
  };
}

export interface TelegramChannelCreateResponse extends TelegramChannel {
  api_key: string; // raw; only shown at create/rotate
}

export interface TelegramTestResult {
  ok: boolean;
  username?: string;
  bot_id?: number;
  first_name?: string;
  error?: string;
}

function baseUrl(): string {
  if (typeof window === 'undefined') {
    return process.env.BACKEND_URL || 'http://api:8000';
  }
  return process.env.NEXT_PUBLIC_BACKEND_URL || window.location.origin;
}

function headers(token: string, json = false): HeadersInit {
  const h: HeadersInit = { Authorization: `Bearer ${token}` };
  if (json) h['Content-Type'] = 'application/json';
  return h;
}

/**
 * Thrown for any non-2xx HTTP response from the IM channels API.
 * Carries the status code so callers can route on auth/permission/etc.
 * without parsing the human-readable message.
 */
export class ImChannelsApiError extends Error {
  readonly status: number;
  readonly detail: string;
  constructor(status: number, detail: string) {
    super(`HTTP ${status} ${detail}`);
    this.name = 'ImChannelsApiError';
    this.status = status;
    this.detail = detail;
  }
}

async function ok<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = '';
    try {
      const body = (await res.json()) as { detail?: unknown };
      detail = String(body.detail ?? '');
    } catch {
      detail = await res.text();
    }
    throw new ImChannelsApiError(res.status, detail || res.statusText);
  }
  return (await res.json()) as T;
}

export async function listTelegramChannels(token: string): Promise<TelegramChannel[]> {
  const res = await fetch(`${baseUrl()}/api/v1/im/channels?type=telegram`, {
    headers: headers(token),
  });
  return ok<TelegramChannel[]>(res);
}

export async function createTelegramChannel(
  token: string,
  body: {
    name: string;
    bot_token: string;
    allowed_user_ids: number[];
    enabled: boolean;
  },
): Promise<TelegramChannelCreateResponse> {
  const res = await fetch(`${baseUrl()}/api/v1/im/channels/telegram`, {
    method: 'POST',
    headers: headers(token, true),
    body: JSON.stringify(body),
  });
  return ok<TelegramChannelCreateResponse>(res);
}

export async function updateTelegramChannel(
  token: string,
  id: number,
  patch: Partial<{
    name: string;
    bot_token: string;
    allowed_user_ids: number[];
    enabled: boolean;
  }>,
): Promise<TelegramChannel> {
  const res = await fetch(`${baseUrl()}/api/v1/im/channels/telegram/${id}`, {
    method: 'PATCH',
    headers: headers(token, true),
    body: JSON.stringify(patch),
  });
  return ok<TelegramChannel>(res);
}

export async function deleteTelegramChannel(
  token: string,
  id: number,
): Promise<void> {
  const res = await fetch(`${baseUrl()}/api/v1/im/channels/telegram/${id}`, {
    method: 'DELETE',
    headers: headers(token),
  });
  if (!res.ok && res.status !== 204) {
    throw new ImChannelsApiError(res.status, await res.text());
  }
}

export async function testTelegramChannel(
  token: string,
  id: number,
): Promise<TelegramTestResult> {
  const res = await fetch(
    `${baseUrl()}/api/v1/im/channels/telegram/${id}/test`,
    { method: 'POST', headers: headers(token) },
  );
  return ok<TelegramTestResult>(res);
}

// --- WhatsApp -----------------------------------------------------------
export interface WhatsAppChannel {
  id: number;
  type: 'whatsapp';
  name: string;
  enabled: boolean;
  config: {
    phone_number_id: string;          // plaintext
    business_account_id?: string;     // plaintext
    graph_version?: string;           // plaintext (e.g. "v20.0")
    access_token?: string;            // masked to last 6 chars
    app_secret?: string;              // masked
    verify_token?: string;            // masked
  };
}

export interface WhatsAppTestResult {
  ok: boolean;
  phone_number?: string;
  verified_name?: string;
  error?: string;
}

export async function listWhatsAppChannels(token: string): Promise<WhatsAppChannel[]> {
  const res = await fetch(`${baseUrl()}/api/v1/im/channels?type=whatsapp`, {
    headers: headers(token),
  });
  return ok<WhatsAppChannel[]>(res);
}

export async function createWhatsAppChannel(
  token: string,
  body: {
    name: string;
    phone_number_id: string;
    access_token: string;
    app_secret: string;
    verify_token: string;
    business_account_id?: string;
    graph_version?: string;
    enabled: boolean;
  },
): Promise<WhatsAppChannel> {
  const res = await fetch(`${baseUrl()}/api/v1/im/channels/whatsapp`, {
    method: 'POST',
    headers: headers(token, true),
    body: JSON.stringify(body),
  });
  return ok<WhatsAppChannel>(res);
}

export async function updateWhatsAppChannel(
  token: string,
  id: number,
  patch: Partial<{
    name: string;
    phone_number_id: string;
    access_token: string;
    app_secret: string;
    verify_token: string;
    business_account_id: string;
    graph_version: string;
    enabled: boolean;
  }>,
): Promise<WhatsAppChannel> {
  const res = await fetch(`${baseUrl()}/api/v1/im/channels/whatsapp/${id}`, {
    method: 'PATCH',
    headers: headers(token, true),
    body: JSON.stringify(patch),
  });
  return ok<WhatsAppChannel>(res);
}

export async function deleteWhatsAppChannel(
  token: string,
  id: number,
): Promise<void> {
  const res = await fetch(`${baseUrl()}/api/v1/im/channels/whatsapp/${id}`, {
    method: 'DELETE',
    headers: headers(token),
  });
  if (!res.ok && res.status !== 204) {
    throw new ImChannelsApiError(res.status, await res.text());
  }
}

export async function testWhatsAppChannel(
  token: string,
  id: number,
): Promise<WhatsAppTestResult> {
  const res = await fetch(
    `${baseUrl()}/api/v1/im/channels/whatsapp/${id}/test`,
    { method: 'POST', headers: headers(token) },
  );
  return ok<WhatsAppTestResult>(res);
}

/**
 * Build the public Meta webhook URL the operator must paste into the
 * Meta Developer Console when subscribing this channel. The path is
 * derived from the channel id; the public origin must be set via
 * NEXT_PUBLIC_PUBLIC_URL (or falls back to window.location.origin in
 * the browser).
 */
export function whatsappWebhookUrl(channelId: number): string {
  const origin =
    process.env.NEXT_PUBLIC_PUBLIC_URL ||
    (typeof window !== 'undefined' ? window.location.origin : '');
  return `${origin}/api/v1/im/channels/whatsapp/${channelId}/webhook`;
}
