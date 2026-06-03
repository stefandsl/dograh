import { routing } from "./routing";

// Helpers for reasoning about locale-prefixed paths (/en/..., /it/...) in
// client code that reads raw window.location / next/navigation pathnames
// (which include the locale segment, unlike next-intl's usePathname).

/** Return the leading locale segment with slash (e.g. "/en") or "" if none. */
export function getLocalePrefix(pathname: string): string {
  const seg = pathname.split("/")[1];
  return (routing.locales as readonly string[]).includes(seg) ? `/${seg}` : "";
}

/** Strip a leading locale segment, always returning a path starting with "/". */
export function stripLocale(pathname: string): string {
  const prefix = getLocalePrefix(pathname);
  if (!prefix) return pathname || "/";
  const rest = pathname.slice(prefix.length);
  return rest === "" ? "/" : rest;
}

/** True if the (locale-stripped) path is an auth page. */
export function isAuthPath(pathname: string): boolean {
  return stripLocale(pathname).startsWith("/auth/");
}

/** Locale-preserving path to the login page for the current pathname. */
export function loginPath(pathname: string): string {
  return `${getLocalePrefix(pathname)}/auth/login`;
}
