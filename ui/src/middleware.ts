import type { NextRequest } from "next/server";
import { NextResponse } from "next/server";
import createMiddleware from "next-intl/middleware";

import { getServerBackendUrl } from "@/lib/apiClient";

import { routing } from "./i18n/routing";

const OSS_TOKEN_COOKIE = "dograh_auth_token";

// Paths that don't require authentication in OSS mode (locale-stripped).
const PUBLIC_PATHS = [
  "/auth/login",
  "/auth/signup",
  "/auth/forgot-password",
  "/auth/reset-password",
];

const intlMiddleware = createMiddleware(routing);

let cachedAuthProvider: string | null = null;

async function fetchAuthProvider(): Promise<string> {
  if (cachedAuthProvider) {
    return cachedAuthProvider;
  }
  try {
    const backendUrl = getServerBackendUrl();
    const res = await fetch(`${backendUrl}/api/v1/health`);
    if (res.ok) {
      const data = await res.json();
      cachedAuthProvider = (data.auth_provider as string) || "local";
      return cachedAuthProvider;
    }
  } catch {
    // Backend not reachable — fall back to local
  }
  cachedAuthProvider = "local";
  return cachedAuthProvider;
}

/** Remove a leading /en or /it segment so auth checks are locale-agnostic. */
function stripLocale(pathname: string): string {
  for (const locale of routing.locales) {
    if (pathname === `/${locale}`) return "/";
    if (pathname.startsWith(`/${locale}/`)) return pathname.slice(locale.length + 1);
  }
  return pathname;
}

/** Resolve the active locale from the first path segment, else default. */
function localeFromPath(pathname: string): string {
  const seg = pathname.split("/")[1];
  return (routing.locales as readonly string[]).includes(seg)
    ? seg
    : routing.defaultLocale;
}

export async function middleware(request: NextRequest) {
  // 1) Locale routing first — next-intl handles prefix detection/redirects and
  //    sets the locale for the request. Preserve its response/headers.
  const response = intlMiddleware(request);

  // 2) Auth gate (OSS/local mode only), operating on the locale-stripped path.
  const authProvider = await fetchAuthProvider();
  if (authProvider !== "local") {
    return response;
  }

  const token = request.cookies.get(OSS_TOKEN_COOKIE)?.value;
  const pathname = stripLocale(request.nextUrl.pathname);

  if (PUBLIC_PATHS.some((p) => pathname.startsWith(p))) {
    return response;
  }

  if (!token) {
    const locale = localeFromPath(request.nextUrl.pathname);
    const loginUrl = new URL(`/${locale}/auth/login`, request.url);
    return NextResponse.redirect(loginUrl);
  }

  return response;
}

export const config = {
  matcher: [
    // Run on everything except API routes, Next internals, the Sentry tunnel
    // (monitoring), favicon, and static assets from /public (served at the URL
    // root, e.g. /dograh-logo.png). Excludes the union of asset extensions both
    // the fork and upstream cover (images + fonts).
    "/((?!api|_next/static|_next/image|favicon.ico|monitoring|.*\\.(?:png|jpe?g|gif|svg|webp|avif|ico|woff2?|ttf|otf)$).*)",
  ],
};
