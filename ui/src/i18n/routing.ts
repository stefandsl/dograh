import { defineRouting } from "next-intl/routing";

// English + Italian bilingual support. `en` is the default and is served
// without a visible prefix would-be option, but we use the standard prefixed
// strategy (/en, /it) so locale is always explicit in the URL.
export const routing = defineRouting({
  locales: ["en", "it"],
  defaultLocale: "en",
});

export type AppLocale = (typeof routing.locales)[number];
