"use client";

import {
  ArrowLeft,
  Copy,
  ExternalLink,
  Pencil,
  Plus,
  Star,
  Trash2,
} from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

import {
  deletePhoneNumberApiV1OrganizationsTelephonyConfigsConfigIdPhoneNumbersPhoneNumberIdDelete,
  getTelephonyConfigurationByIdApiV1OrganizationsTelephonyConfigsConfigIdGet,
  listPhoneNumbersApiV1OrganizationsTelephonyConfigsConfigIdPhoneNumbersGet,
  setDefaultCallerIdApiV1OrganizationsTelephonyConfigsConfigIdPhoneNumbersPhoneNumberIdSetDefaultCallerPost,
  setDefaultOutboundApiV1OrganizationsTelephonyConfigsConfigIdSetDefaultOutboundPost,
} from "@/client/sdk.gen";
import type {
  PhoneNumberResponse,
  TelephonyConfigurationDetail,
} from "@/client/types.gen";
import { ConfigFormDialog } from "@/components/telephony/ConfigFormDialog";
import { PhoneNumberDialog } from "@/components/telephony/PhoneNumberDialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Link } from "@/i18n/navigation";
import { detailFromError } from "@/lib/apiError";
import { useAuth } from "@/lib/auth";

const INBOUND_WEBHOOK_PATH = "/api/v1/telephony/inbound/run";

function getInboundWebhookUrl(): string {
  const backendUrl =
    process.env.NEXT_PUBLIC_BACKEND_URL ||
    (typeof window !== "undefined" ? window.location.origin : "");
  return `${backendUrl}${INBOUND_WEBHOOK_PATH}`;
}

export default function TelephonyConfigurationDetailPage() {
  const t = useTranslations("pages.telephonyConfigurations.configId");
  const router = useRouter();
  const params = useParams<{ configId: string }>();
  const configId = Number(params.configId);

  const { user, getAccessToken, loading: authLoading } = useAuth();
  const [config, setConfig] = useState<TelephonyConfigurationDetail | null>(null);
  const [phoneNumbers, setPhoneNumbers] = useState<PhoneNumberResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [editConfigOpen, setEditConfigOpen] = useState(false);

  const [phoneDialogOpen, setPhoneDialogOpen] = useState(false);
  const [phoneEditTarget, setPhoneEditTarget] = useState<PhoneNumberResponse | null>(
    null,
  );
  const [phoneDeleteTarget, setPhoneDeleteTarget] = useState<PhoneNumberResponse | null>(
    null,
  );

  const fetchAll = useCallback(async () => {
    if (authLoading || !user || !configId) return;
    setLoading(true);
    try {
      const token = await getAccessToken();
      const [cfgRes, numbersRes] = await Promise.all([
        getTelephonyConfigurationByIdApiV1OrganizationsTelephonyConfigsConfigIdGet({
          headers: { Authorization: `Bearer ${token}` },
          path: { config_id: configId },
        }),
        listPhoneNumbersApiV1OrganizationsTelephonyConfigsConfigIdPhoneNumbersGet({
          headers: { Authorization: `Bearer ${token}` },
          path: { config_id: configId },
        }),
      ]);

      if (cfgRes.error) throw new Error(detailFromError(cfgRes.error));
      if (numbersRes.error) throw new Error(detailFromError(numbersRes.error));

      setConfig(cfgRes.data ?? null);
      setPhoneNumbers(numbersRes.data?.phone_numbers ?? []);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("toastLoadError"));
    } finally {
      setLoading(false);
    }
  }, [authLoading, user, configId, getAccessToken]);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  const onSetDefaultOutbound = async () => {
    if (!config) return;
    try {
      const token = await getAccessToken();
      const res = await setDefaultOutboundApiV1OrganizationsTelephonyConfigsConfigIdSetDefaultOutboundPost(
        {
          headers: { Authorization: `Bearer ${token}` },
          path: { config_id: config.id },
        },
      );
      if (res.error) throw new Error(detailFromError(res.error));
      toast.success(t("toastSetDefaultOutbound"));
      fetchAll();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("toastSetDefaultError"));
    }
  };

  const onSetDefaultCaller = async (n: PhoneNumberResponse) => {
    try {
      const token = await getAccessToken();
      const res = await setDefaultCallerIdApiV1OrganizationsTelephonyConfigsConfigIdPhoneNumbersPhoneNumberIdSetDefaultCallerPost(
        {
          headers: { Authorization: `Bearer ${token}` },
          path: { config_id: configId, phone_number_id: n.id },
        },
      );
      if (res.error) throw new Error(detailFromError(res.error));
      toast.success(t("toastSetDefaultCaller", { address: n.address }));
      fetchAll();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("toastSetDefaultCallerError"));
    }
  };

  const onConfirmDeletePhone = async () => {
    if (!phoneDeleteTarget) return;
    try {
      const token = await getAccessToken();
      const res = await deletePhoneNumberApiV1OrganizationsTelephonyConfigsConfigIdPhoneNumbersPhoneNumberIdDelete(
        {
          headers: { Authorization: `Bearer ${token}` },
          path: {
            config_id: configId,
            phone_number_id: phoneDeleteTarget.id,
          },
        },
      );
      if (res.error) throw new Error(detailFromError(res.error));
      toast.success(t("toastPhoneDeleted"));
      setPhoneDeleteTarget(null);
      fetchAll();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("toastPhoneDeleteError"));
    }
  };

  if (loading) {
    return (
      <div className="container mx-auto px-4 py-8 space-y-3">
        <Skeleton className="h-10 w-1/3" />
        <Skeleton className="h-32 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (!config) {
    return (
      <div className="container mx-auto px-4 py-8">
        <Button variant="ghost" onClick={() => router.push("/telephony-configurations")}>
          <ArrowLeft className="h-4 w-4 mr-2" /> {t("back")}
        </Button>
        <p className="mt-4 text-muted-foreground">{t("configNotFound")}</p>
      </div>
    );
  }

  return (
    <div className="container mx-auto px-4 py-8 space-y-6">
      <div>
        <Link
          href="/telephony-configurations"
          className="inline-flex items-center text-sm text-muted-foreground hover:underline"
        >
          <ArrowLeft className="h-4 w-4 mr-1" /> {t("allConfigurations")}
        </Link>
      </div>

      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-4">
          <div className="space-y-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <CardTitle className="truncate">{config.name}</CardTitle>
              <Badge variant="secondary">{config.provider}</Badge>
              {config.is_default_outbound && (
                <Badge className="gap-1">
                  <Star className="h-3 w-3 fill-current" />
                  {t("defaultBadge")}
                </Badge>
              )}
            </div>
            <CardDescription>
              {t("updated", { date: new Date(config.updated_at).toLocaleString() })}
            </CardDescription>
            <button
              type="button"
              onClick={() => {
                navigator.clipboard
                  .writeText(String(config.id))
                  .then(() => toast.success(t("toastConfigIdCopied")))
                  .catch(() => toast.error(t("toastCopyIdError")));
              }}
              title={t("clickToCopy")}
              className="inline-flex items-center gap-1 self-start rounded font-mono text-xs text-muted-foreground hover:text-foreground"
            >
              <span className="truncate">{t("configIdLabel", { id: config.id })}</span>
              <Copy className="h-3 w-3 shrink-0" />
            </button>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {!config.is_default_outbound && (
              <Button variant="outline" size="sm" onClick={onSetDefaultOutbound}>
                <Star className="h-4 w-4 mr-2" /> {t("setAsDefault")}
              </Button>
            )}
            <Button variant="outline" size="sm" onClick={() => setEditConfigOpen(true)}>
              <Pencil className="h-4 w-4 mr-2" /> {t("editCredentials")}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm">
            {Object.entries(config.credentials ?? {}).map(([k, v]) => (
              <div key={k} className="flex justify-between gap-3">
                <dt className="text-muted-foreground">{k}</dt>
                <dd className="font-mono text-right truncate max-w-[60%]">
                  {String(v ?? "")}
                </dd>
              </div>
            ))}
          </dl>
          <div className="space-y-1">
            <p className="text-xs text-muted-foreground">{t("inboundWebhookUrl")}</p>
            <button
              type="button"
              onClick={() => {
                const url = getInboundWebhookUrl();
                navigator.clipboard
                  .writeText(url)
                  .then(() => toast.success(t("toastWebhookUrlCopied")))
                  .catch(() => toast.error(t("toastCopyUrlError")));
              }}
              title={t("clickToCopyWebhookUrl")}
              aria-label={t("copyWebhookUrlAria")}
              className="inline-flex items-center gap-1 self-start rounded font-mono text-xs text-muted-foreground hover:text-foreground"
            >
              <span className="truncate">{getInboundWebhookUrl()}</span>
              <Copy className="h-3 w-3 shrink-0" />
            </button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-start justify-between gap-4">
          <div className="space-y-1">
            <CardTitle>{t("phoneNumbersTitle")}</CardTitle>
            <CardDescription>
              {t("phoneNumbersDescription")}{" "}
              <a
                href="https://docs.dograh.com/integrations/telephony/inbound"
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-0.5 underline"
              >
                {t("inboundDocs")} <ExternalLink className="h-3 w-3" />
              </a>
            </CardDescription>
          </div>
          <Button
            size="sm"
            onClick={() => {
              setPhoneEditTarget(null);
              setPhoneDialogOpen(true);
            }}
          >
            <Plus className="h-4 w-4 mr-2" /> {t("addPhoneNumber")}
          </Button>
        </CardHeader>
        <CardContent>
          {phoneNumbers.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t("noPhoneNumbers")}</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t("tableAddress")}</TableHead>
                  <TableHead>{t("tableType")}</TableHead>
                  <TableHead>{t("tableLabel")}</TableHead>
                  <TableHead>{t("tableStatus")}</TableHead>
                  <TableHead>{t("tableInboundWorkflow")}</TableHead>
                  <TableHead className="text-right">{t("tableActions")}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {phoneNumbers.map((n) => (
                  <TableRow key={n.id}>
                    <TableCell className="font-mono">{n.address}</TableCell>
                    <TableCell>
                      <Badge variant="outline">{n.address_type}</Badge>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {n.label ?? "-"}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {n.is_active ? (
                          <Badge variant="secondary">{t("active")}</Badge>
                        ) : (
                          <Badge variant="outline">{t("inactive")}</Badge>
                        )}
                        {n.is_default_caller_id && (
                          <Badge className="gap-1">
                            <Star className="h-3 w-3 fill-current" /> {t("defaultCaller")}
                          </Badge>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {n.inbound_workflow_id ? (
                        <Link
                          href={`/workflow/${n.inbound_workflow_id}`}
                          className="inline-flex items-center gap-1 hover:underline hover:text-foreground"
                        >
                          <span>#{n.inbound_workflow_id}</span>
                          {n.inbound_workflow_name && (
                            <span
                              className="truncate max-w-[160px]"
                              title={n.inbound_workflow_name}
                            >
                              {n.inbound_workflow_name.length > 24
                                ? `${n.inbound_workflow_name.slice(0, 24)}…`
                                : n.inbound_workflow_name}
                            </span>
                          )}
                        </Link>
                      ) : (
                        "-"
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        {!n.is_default_caller_id && n.is_active && (
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => onSetDefaultCaller(n)}
                            title={t("setAsDefaultCallerId")}
                          >
                            <Star className="h-4 w-4" />
                          </Button>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setPhoneEditTarget(n);
                            setPhoneDialogOpen(true);
                          }}
                          title={t("edit")}
                        >
                          <Pencil className="h-4 w-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setPhoneDeleteTarget(n)}
                          title={t("delete")}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <ConfigFormDialog
        open={editConfigOpen}
        onOpenChange={setEditConfigOpen}
        existing={config}
        onSaved={fetchAll}
      />

      <PhoneNumberDialog
        open={phoneDialogOpen}
        onOpenChange={setPhoneDialogOpen}
        configId={configId}
        existing={phoneEditTarget}
        onSaved={fetchAll}
      />

      <AlertDialog
        open={!!phoneDeleteTarget}
        onOpenChange={(o) => !o && setPhoneDeleteTarget(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{t("deletePhoneTitle")}</AlertDialogTitle>
            <AlertDialogDescription>
              {t("deletePhoneDescription", { address: phoneDeleteTarget?.address ?? "" })}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{t("cancel")}</AlertDialogCancel>
            <AlertDialogAction onClick={onConfirmDeletePhone}>{t("delete")}</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
