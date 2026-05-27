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

async function ok<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = '';
    try {
      const body = (await res.json()) as { detail?: unknown };
      detail = String(body.detail ?? '');
    } catch {
      detail = await res.text();
    }
    throw new Error(`HTTP ${res.status} ${detail || res.statusText}`);
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
    throw new Error(`HTTP ${res.status} ${await res.text()}`);
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
