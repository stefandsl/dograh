"use client";

import { Languages } from "lucide-react";
import { useLocale, useTranslations } from "next-intl";
import { useTransition } from "react";

import { Button } from "@/components/ui/button";
import { usePathname, useRouter } from "@/i18n/navigation";
import { cn } from "@/lib/utils";

interface LanguageSwitcherProps {
  className?: string;
  showLabel?: boolean;
  variant?: "ghost" | "outline" | "default";
  size?: "default" | "sm" | "lg" | "icon";
}

// Toggles the active locale between English and Italian, keeping the user on the
// current page. Locale lives in the URL prefix (/en, /it); next-intl's
// locale-aware router rewrites only the prefix.
export default function LanguageSwitcher({
  className,
  showLabel = false,
  variant = "ghost",
  size = "icon",
}: LanguageSwitcherProps) {
  const t = useTranslations("common");
  const locale = useLocale();
  const pathname = usePathname();
  const router = useRouter();
  const [isPending, startTransition] = useTransition();

  const next = locale === "en" ? "it" : "en";
  const currentName = locale === "it" ? t("italian") : t("english");

  const toggleLanguage = () => {
    startTransition(() => {
      // Re-render the current path under the other locale.
      router.replace(pathname, { locale: next });
    });
  };

  return (
    <Button
      variant={variant}
      size={size}
      disabled={isPending}
      aria-label={t("switchLanguage")}
      title={t("switchLanguage")}
      className={cn(showLabel && "w-full justify-start", className)}
      onClick={toggleLanguage}
    >
      <Languages className="h-4 w-4" />
      {showLabel ? (
        <span className="ml-2">{currentName}</span>
      ) : (
        <span className="ml-1 text-xs font-medium uppercase">{locale}</span>
      )}
    </Button>
  );
}
