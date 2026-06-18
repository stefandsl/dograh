import type { NextRequest } from 'next/server';

/**
 * Whether OSS auth cookies should include the Secure attribute.
 *
 * Do not use `process.env.NODE_ENV === 'production'` here: Next.js inlines that
 * at build time (often to `true`), which breaks HTTP-only OSS installs and
 * embedded browsers that load the app over plain HTTP.
 */
function requestIsHttps(request: NextRequest): boolean {
  const forwarded = request.headers.get('x-forwarded-proto');
  if (forwarded) {
    return forwarded.split(',')[0]?.trim() === 'https';
  }
  return request.nextUrl.protocol === 'https:';
}

export function authCookieSecure(request: NextRequest): boolean {
  const override = process.env.AUTH_COOKIE_SECURE;
  if (override === 'true') return true;
  if (override === 'false') return false;
  return requestIsHttps(request);
}

export function authCookieBaseOptions(request: NextRequest) {
  return {
    httpOnly: true,
    secure: authCookieSecure(request),
    sameSite: 'lax' as const,
    path: '/',
  };
}
