"use client";

import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import {
  deleteLangfuseCredentialsApiV1OrganizationsLangfuseCredentialsDelete,
  getLangfuseCredentialsApiV1OrganizationsLangfuseCredentialsGet,
  saveLangfuseCredentialsApiV1OrganizationsLangfuseCredentialsPost,
} from "@/client/sdk.gen";
import type { LangfuseCredentialsResponse } from "@/client/types.gen";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/lib/auth";

export function TelemetrySection() {
  const t = useTranslations("components.telemetrySection");
  const { user, loading: authLoading } = useAuth();
  const [credentials, setCredentials] = useState<LangfuseCredentialsResponse>({
    host: "",
    public_key: "",
    secret_key: "",
    configured: false,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const hasFetched = useRef(false);

  useEffect(() => {
    if (authLoading || !user || hasFetched.current) {
      return;
    }
    hasFetched.current = true;
    fetchCredentials();
  }, [authLoading, user]);

  async function fetchCredentials() {
    try {
      const { data } = await getLangfuseCredentialsApiV1OrganizationsLangfuseCredentialsGet();
      if (data) {
        setCredentials(data);
      }
    } catch {
      // No credentials configured yet — that's fine
    } finally {
      setLoading(false);
    }
  }

  async function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    try {
      const { error } = await saveLangfuseCredentialsApiV1OrganizationsLangfuseCredentialsPost({
        body: {
          host: credentials.host ?? "",
          public_key: credentials.public_key ?? "",
          secret_key: credentials.secret_key ?? "",
        },
      });
      if (error) {
        throw new Error("Failed to save");
      }
      toast.success(t("toastSaved"));
      await fetchCredentials();
    } catch {
      toast.error(t("toastSaveError"));
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    setSaving(true);
    try {
      await deleteLangfuseCredentialsApiV1OrganizationsLangfuseCredentialsDelete();
      setCredentials({ host: "", public_key: "", secret_key: "", configured: false });
      toast.success(t("toastRemoved"));
    } catch {
      toast.error(t("toastRemoveError"));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return <p className="text-sm text-muted-foreground">{t("loading")}</p>;
  }

  return (
    <form onSubmit={handleSave} className="space-y-4">
      <p className="text-sm text-muted-foreground">
        {t("description")}
      </p>
      <div className="space-y-2">
        <Label htmlFor="langfuse-host">{t("hostLabel")}</Label>
        <Input
          id="langfuse-host"
          placeholder="https://cloud.langfuse.com"
          value={credentials.host}
          onChange={(e) => setCredentials({ ...credentials, host: e.target.value })}
          required
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="langfuse-public-key">{t("publicKeyLabel")}</Label>
        <Input
          id="langfuse-public-key"
          placeholder="pk-lf-..."
          value={credentials.public_key}
          onChange={(e) => setCredentials({ ...credentials, public_key: e.target.value })}
          required
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="langfuse-secret-key">{t("secretKeyLabel")}</Label>
        <Input
          id="langfuse-secret-key"
          type="password"
          placeholder="sk-lf-..."
          value={credentials.secret_key}
          onChange={(e) => setCredentials({ ...credentials, secret_key: e.target.value })}
          required
        />
      </div>
      <div className="flex gap-2">
        <Button type="submit" disabled={saving}>
          {saving ? t("saving") : t("save")}
        </Button>
        {credentials.configured && (
          <Button type="button" variant="destructive" disabled={saving} onClick={handleDelete}>
            {t("remove")}
          </Button>
        )}
      </div>
    </form>
  );
}
