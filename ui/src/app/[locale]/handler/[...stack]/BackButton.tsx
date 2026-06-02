"use client";

import { ArrowLeft } from "lucide-react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";

import { Button } from "@/components/ui/button";

export function BackButton() {
  const router = useRouter();
  const t = useTranslations("components.backButton");

  return (
    <header className="flex items-center border-b px-4 py-3">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => router.back()}
        className="gap-2"
      >
        <ArrowLeft className="h-4 w-4" />
        {t("goBack")}
      </Button>
    </header>
  );
}
