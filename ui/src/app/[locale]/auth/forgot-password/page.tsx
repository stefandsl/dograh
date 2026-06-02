"use client";

import { useTranslations } from "next-intl";
import { useState } from "react";
import { toast } from "sonner";

import { client } from "@/client/client.gen";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Link } from "@/i18n/navigation";

interface ForgotPasswordResponse {
  message: string;
  reset_url?: string | null;
}

export default function ForgotPasswordPage() {
  const t = useTranslations("auth.forgot");
  const tc = useTranslations("common");
  const [email, setEmail] = useState("");
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  // Populated only in dev/self-host without SMTP configured.
  const [devResetUrl, setDevResetUrl] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);

    try {
      const res = await client.post({
        url: "/api/v1/auth/forgot-password",
        body: { email },
      });

      if (res.error) {
        const detail = (res.error as { detail?: string })?.detail;
        toast.error(detail || tc("errorGeneric"));
        return;
      }

      const data = res.data as ForgotPasswordResponse | undefined;
      setDevResetUrl(data?.reset_url ?? null);
      setSubmitted(true);
    } catch {
      toast.error(tc("errorGeneric"));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <CardTitle className="text-2xl">{t("title")}</CardTitle>
          <CardDescription>{t("subtitle")}</CardDescription>
        </CardHeader>
        <CardContent>
          {submitted ? (
            <div className="space-y-4">
              <p className="text-center text-sm text-muted-foreground">
                {t("sent", { email })}
              </p>
              {devResetUrl && (
                <div className="rounded-md border border-dashed p-3 text-sm">
                  <p className="mb-1 font-medium">{t("devMode")}</p>
                  <a
                    href={devResetUrl}
                    className="break-all text-primary underline-offset-4 hover:underline"
                  >
                    {devResetUrl}
                  </a>
                </div>
              )}
            </div>
          ) : (
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
              <Button type="submit" className="w-full" disabled={loading}>
                {loading ? t("submitting") : t("submit")}
              </Button>
            </form>
          )}
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
