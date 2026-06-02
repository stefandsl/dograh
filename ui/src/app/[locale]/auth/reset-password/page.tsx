"use client";

import { useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { Suspense, useState } from "react";
import { toast } from "sonner";

import { client } from "@/client/client.gen";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Link } from "@/i18n/navigation";

interface ResetPasswordResponse {
  token: string;
  user: unknown;
}

function ResetPasswordForm() {
  const t = useTranslations("auth.reset");
  const tc = useTranslations("common");
  const locale = useLocale();
  const searchParams = useSearchParams();
  const token = searchParams.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (password.length < 8) {
      toast.error(t("passwordTooShort"));
      return;
    }
    if (password !== confirmPassword) {
      toast.error(t("passwordMismatch"));
      return;
    }

    setLoading(true);
    try {
      const res = await client.post({
        url: "/api/v1/auth/reset-password",
        body: { token, password },
      });

      if (res.error || !res.data) {
        const detail = (res.error as { detail?: string })?.detail;
        toast.error(detail || t("failed"));
        return;
      }

      const data = res.data as ResetPasswordResponse;

      // Set httpOnly cookies via server route, same as the login flow.
      await fetch("/api/auth/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: data.token, user: data.user }),
      });

      toast.success(t("success"));
      window.location.href = `/${locale}/after-sign-in`;
    } catch {
      toast.error(tc("errorGeneric"));
    } finally {
      setLoading(false);
    }
  };

  if (!token) {
    return (
      <div className="space-y-4 text-center">
        <p className="text-sm text-muted-foreground">{t("invalidLink")}</p>
        <Button asChild className="w-full">
          <Link href="/auth/forgot-password">{t("requestNew")}</Link>
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="password">{t("newPassword")}</Label>
        <Input
          id="password"
          type="password"
          placeholder={t("newPasswordPlaceholder")}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="confirmPassword">{t("confirmPassword")}</Label>
        <Input
          id="confirmPassword"
          type="password"
          placeholder={t("confirmPasswordPlaceholder")}
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          required
        />
      </div>
      <Button type="submit" className="w-full" disabled={loading}>
        {loading ? t("submitting") : t("submit")}
      </Button>
    </form>
  );
}

export default function ResetPasswordPage() {
  const t = useTranslations("auth.reset");
  const tc = useTranslations("common");
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">{t("title")}</CardTitle>
          <CardDescription>{t("subtitle")}</CardDescription>
        </CardHeader>
        <CardContent>
          <Suspense fallback={<div className="text-center text-sm text-muted-foreground">{tc("loading")}</div>}>
            <ResetPasswordForm />
          </Suspense>
          <p className="mt-4 text-center text-sm text-muted-foreground">
            {t("remember")}{" "}
            <Link href="/auth/login" className="text-primary underline-offset-4 hover:underline">
              {t("loginLink")}
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
