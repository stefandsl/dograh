"use client";

import { useLocale, useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";

import { loginApiV1AuthLoginPost } from "@/client/sdk.gen";
import { AuthEnterpriseCTA } from "@/components/auth/AuthEnterpriseCTA";
import { AuthShell } from "@/components/auth/AuthShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Link } from "@/i18n/navigation";

export default function LoginPage() {
  const t = useTranslations("auth.login");
  const tc = useTranslations("common");
  const locale = useLocale();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const res = await loginApiV1AuthLoginPost({
        body: { email, password },
      });

      if (res.error || !res.data) {
        const detail = (res.error as { detail?: string })?.detail;
        toast.error(detail || t("failed"));
        return;
      }

      // Set httpOnly cookies via server route
      const sessionRes = await fetch("/api/auth/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: res.data.token, user: res.data.user }),
      });

      if (!sessionRes.ok) {
        toast.error(t("failed"));
        return;
      }

      window.location.href = `/${locale}/after-sign-in`;
    } catch {
      toast.error(tc("errorGeneric"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <AuthShell enterpriseSlot={<AuthEnterpriseCTA />}>
      <div className="space-y-1.5 text-center">
        <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
        <p className="text-sm text-muted-foreground">{t("subtitle")}</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="email">{t("email")}</Label>
          <Input
            id="email"
            type="email"
            placeholder={t("emailPlaceholder")}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">{t("password")}</Label>
          <Input
            id="password"
            type="password"
            placeholder={t("passwordPlaceholder")}
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>
        <Button type="submit" className="w-full" disabled={loading}>
          {loading ? t("submitting") : t("submit")}
        </Button>
      </form>

      <p className="text-center text-sm">
        <Link
          href="/auth/forgot-password"
          className="text-primary underline-offset-4 hover:underline"
        >
          {t("forgot")}
        </Link>
      </p>

      <p className="text-center text-sm text-muted-foreground">
        {t("noAccount")}{" "}
        <Link href="/auth/signup" className="text-primary underline-offset-4 hover:underline">
          {t("signupLink")}
        </Link>
      </p>
    </AuthShell>
  );
}
