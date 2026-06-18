import { NextRequest, NextResponse } from 'next/server';

import { authCookieBaseOptions } from '@/lib/auth/cookieOptions';

const OSS_TOKEN_COOKIE = 'dograh_auth_token';
const OSS_USER_COOKIE = 'dograh_auth_user';

export async function POST(request: NextRequest) {
  const cookieOptions = authCookieBaseOptions(request);
  const response = NextResponse.json({ success: true });

  response.cookies.set(OSS_TOKEN_COOKIE, '', {
    ...cookieOptions,
    maxAge: 0,
  });

  response.cookies.set(OSS_USER_COOKIE, '', {
    ...cookieOptions,
    maxAge: 0,
  });

  return response;
}
