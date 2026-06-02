import { hasLocale } from "next-intl";
import { getRequestConfig } from "next-intl/server";

import { routing } from "./routing";

// Per-request config consumed by next-intl's server layer. Resolves the active
// locale from the URL segment and loads the matching message catalog.
export default getRequestConfig(async ({ requestLocale }) => {
  const requested = await requestLocale;
  const locale = hasLocale(routing.locales, requested)
    ? requested
    : routing.defaultLocale;

  return {
    locale,
    messages: (await import(`../../messages/${locale}.json`)).default,
  };
});
