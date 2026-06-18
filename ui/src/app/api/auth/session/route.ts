import { NextRequest, NextResponse } from 'next/server';

import { authCookieBaseOptions } from '@/lib/auth/cookieOptions';

const OSS_TOKEN_COOKIE = 'dograh_auth_token';
const OSS_USER_COOKIE = 'dograh_auth_user';

export async function POST(request: NextRequest) {
  const { token, user } = await request.json();

  if (!token) {
    return NextResponse.json({ error: 'Missing token' }, { status: 400 });
  }

  const cookieOptions = authCookieBaseOptions(request);
  const response = NextResponse.json({ success: true });

  response.cookies.set(OSS_TOKEN_COOKIE, token, {
    ...cookieOptions,
    maxAge: 60 * 60 * 24 * 30,
  });

  response.cookies.set(OSS_USER_COOKIE, JSON.stringify(user), {
    ...cookieOptions,
    maxAge: 60 * 60 * 24 * 30,
  });

  return response;
}
