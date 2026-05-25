"use client";

import { MessageCircle, Pencil, Phone, Plus, Trash2, Zap } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";

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
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { useAuth } from "@/lib/auth";
import {
  createTelegramSipConfig,
  deleteTelegramSipConfig,
  getTelegramSipConfig,
  initiateTelegramSipCall,
  listTelegramSipCalls,
  listTelegramSipConfigs,
  testTelegramSipConfig,
  updateTelegramSipConfig,
  type GatewayProviderType,
  type TelegramSipCallLog,
  type TelegramSipConfigDetail,
  type TelegramSipConfigListItem,
  type TelegramSipCredentials,
} from "@/lib/telegram-sip-gateway-api";

const EMPTY_CREDENTIALS: TelegramSipCredentials = {
  sip_host: "",
  sip_port: 5060,
  sip_username: "",
  sip_password: "",
  sip_caller_id: "",
  telegram_destination_id: "",
  webhook_callback_url: "",
  gateway_api_base_url: "",
  gateway_api_key: "",
};

const PROVIDER_LABELS: Record<GatewayProviderType, string> = {
  sip_tg: "SIP.TG",
  tg2sip: "tg2sip",
  custom: "Custom REST gateway",
};

function isMasked(value: string) {
  return value.includes("***");
}

export default function TelegramSipGatewayPage() {
  const { user, getAccessToken, loading: authLoading } = useAuth();
  const [items, setItems] = useState<TelegramSipConfigListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [formOpen, setFormOpen] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [providerType, setProviderType] = useState<GatewayProviderType>("custom");
  const [isEnabled, setIsEnabled] = useState(true);
  const [credentials, setCredentials] =
    useState<TelegramSipCredentials>(EMPTY_CREDENTIALS);
  const [submitting, setSubmitting] = useState(false);
  const [deleteTarget, setDeleteTarget] =
    useState<TelegramSipConfigListItem | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [callDestination, setCallDestination] = useState("");
  const [callLogs, setCallLogs] = useState<TelegramSipCallLog[]>([]);
  const [testingId, setTestingId] = useState<number | null>(null);

  const fetchItems = useCallback(async () => {
    if (authLoading || !user) return;
    setLoading(true);
    try {
      const token = await getAccessToken();
      const res = await listTelegramSipConfigs(token);
      setItems(res.configurations);
      if (res.configurations.length && selectedId === null) {
        setSelectedId(res.configurations[0].id);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load gateways");
    } finally {
      setLoading(false);
    }
  }, [authLoading, user, getAccessToken, selectedId]);

  const fetchCalls = useCallback(
    async (configId: number) => {
      const token = await getAccessToken();
      const res = await listTelegramSipCalls(token, configId);
      setCallLogs(res.call_logs);
    },
    [getAccessToken],
  );

  useEffect(() => {
    fetchItems();
  }, [fetchItems]);

  useEffect(() => {
    if (selectedId) fetchCalls(selectedId).catch(() => setCallLogs([]));
  }, [selectedId, fetchCalls]);

  const openCreate = () => {
    setEditId(null);
    setName("");
    setProviderType("custom");
    setIsEnabled(true);
    setCredentials(EMPTY_CREDENTIALS);
    setFormOpen(true);
  };

  const openEdit = async (item: TelegramSipConfigListItem) => {
    try {
      const token = await getAccessToken();
      const detail = await getTelegramSipConfig(token, item.id);
      setEditId(detail.id);
      setName(detail.name);
      setProviderType(detail.gateway_provider_type as GatewayProviderType);
      setIsEnabled(detail.is_enabled);
      setCredentials({ ...EMPTY_CREDENTIALS, ...detail.credentials });
      setFormOpen(true);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to load gateway");
    }
  };

  const onSave = async () => {
    setSubmitting(true);
    try {
      const token = await getAccessToken();
      const credPayload = { ...credentials };
      if (editId) {
        const existing = await getTelegramSipConfig(token, editId);
        if (isMasked(credPayload.sip_password)) {
          credPayload.sip_password = existing.credentials.sip_password;
        }
        if (credPayload.gateway_api_key && isMasked(credPayload.gateway_api_key)) {
          credPayload.gateway_api_key =
            existing.credentials.gateway_api_key ?? "";
        }
        await updateTelegramSipConfig(token, editId, {
          name,
          gateway_provider_type: providerType,
          credentials: credPayload,
          is_enabled: isEnabled,
        });
        toast.success("Gateway updated");
      } else {
        await createTelegramSipConfig(token, {
          name,
          gateway_provider_type: providerType,
          credentials: credPayload,
          is_enabled: isEnabled,
        });
        toast.success("Gateway created");
      }
      setFormOpen(false);
      await fetchItems();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSubmitting(false);
    }
  };

  const onDelete = async () => {
    if (!deleteTarget) return;
    try {
      const token = await getAccessToken();
      await deleteTelegramSipConfig(token, deleteTarget.id);
      toast.success("Gateway deleted");
      if (selectedId === deleteTarget.id) setSelectedId(null);
      setDeleteTarget(null);
      await fetchItems();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to delete");
    }
  };

  const onTest = async (configId: number) => {
    setTestingId(configId);
    try {
      const token = await getAccessToken();
      const res = await testTelegramSipConfig(token, configId);
      if (res.ok) {
        toast.success(
          res.latency_ms
            ? `${res.message} (${res.latency_ms} ms)`
            : res.message,
        );
      } else {
        toast.error(res.message);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Connection test failed");
    } finally {
      setTestingId(null);
    }
  };

  const onCall = async () => {
    if (!selectedId || !callDestination.trim()) return;
    try {
      const token = await getAccessToken();
      const log = await initiateTelegramSipCall(
        token,
        selectedId,
        callDestination.trim(),
      );
      toast.success(`Call ${log.status}${log.gateway_call_id ? ` (${log.gateway_call_id})` : ""}`);
      await fetchCalls(selectedId);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to initiate call");
    }
  };

  const selected = items.find((i) => i.id === selectedId);

  return (
    <div className="container mx-auto px-4 py-8 max-w-5xl">
      <div className="flex justify-between items-start mb-6 gap-4">
        <div>
          <h1 className="text-2xl font-semibold flex items-center gap-2">
            <MessageCircle className="h-7 w-7" />
            Telegram SIP Gateway
          </h1>
          <p className="text-muted-foreground mt-1 text-sm max-w-2xl">
            Telegram does not support SIP natively. Connect an external gateway
            (SIP.TG, tg2sip, or custom) to place and receive calls via SIP.
          </p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="h-4 w-4 mr-2" />
          Add gateway
        </Button>
      </div>

      {loading ? (
        <Skeleton className="h-48 w-full" />
      ) : items.length === 0 ? (
        <Card>
          <CardHeader>
            <CardTitle>No gateways configured</CardTitle>
            <CardDescription>
              Add a SIP-to-Telegram gateway to test connectivity and place calls.
            </CardDescription>
          </CardHeader>
        </Card>
      ) : (
        <div className="grid gap-6 md:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle>Gateways</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2">
              {items.map((item) => (
                <div
                  key={item.id}
                  className={`flex items-center justify-between p-3 rounded-md border cursor-pointer ${
                    selectedId === item.id ? "border-primary bg-muted/50" : ""
                  }`}
                  onClick={() => setSelectedId(item.id)}
                >
                  <div>
                    <div className="font-medium">{item.name}</div>
                    <div className="text-xs text-muted-foreground">
                      {PROVIDER_LABELS[item.gateway_provider_type as GatewayProviderType] ??
                        item.gateway_provider_type}
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <Badge variant={item.is_enabled ? "default" : "secondary"}>
                      {item.is_enabled ? "Enabled" : "Disabled"}
                    </Badge>
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={(e) => {
                        e.stopPropagation();
                        onTest(item.id);
                      }}
                      disabled={testingId === item.id}
                    >
                      <Zap className="h-4 w-4" />
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={(e) => {
                        e.stopPropagation();
                        openEdit(item);
                      }}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      onClick={(e) => {
                        e.stopPropagation();
                        setDeleteTarget(item);
                      }}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Phone className="h-5 w-5" />
                {selected ? selected.name : "Actions"}
              </CardTitle>
              <CardDescription>
                Test the gateway, initiate a Telegram call, and review recent logs.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {selected && (
                <>
                  <div className="rounded-md border bg-muted/30 p-3 text-xs space-y-1 font-mono break-all">
                    <p className="text-muted-foreground font-sans font-normal mb-2">
                      Register these webhook URLs with your gateway:
                    </p>
                    <p>
                      <span className="text-muted-foreground">Inbound: </span>
                      {typeof window !== "undefined"
                        ? `${window.location.origin}/api/v1/telegram-sip-gateway/webhooks/${selected.id}/incoming`
                        : `/api/v1/telegram-sip-gateway/webhooks/${selected.id}/incoming`}
                    </p>
                    <p>
                      <span className="text-muted-foreground">Status: </span>
                      {typeof window !== "undefined"
                        ? `${window.location.origin}/api/v1/telegram-sip-gateway/webhooks/${selected.id}/status`
                        : `/api/v1/telegram-sip-gateway/webhooks/${selected.id}/status`}
                    </p>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="destination">Call destination</Label>
                    <div className="flex gap-2">
                      <Input
                        id="destination"
                        placeholder="@username or routing ID"
                        value={callDestination}
                        onChange={(e) => setCallDestination(e.target.value)}
                      />
                      <Button onClick={onCall} disabled={!callDestination.trim()}>
                        Call
                      </Button>
                    </div>
                  </div>
                  <div>
                    <h3 className="text-sm font-medium mb-2">Recent calls</h3>
                    {callLogs.length === 0 ? (
                      <p className="text-sm text-muted-foreground">No calls yet.</p>
                    ) : (
                      <ul className="text-sm space-y-2 max-h-48 overflow-y-auto">
                        {callLogs.map((log) => (
                          <li
                            key={log.id}
                            className="flex justify-between border-b pb-1"
                          >
                            <span>
                              {log.direction} → {log.destination}
                            </span>
                            <Badge
                              variant={
                                log.status === "failed" ? "destructive" : "outline"
                              }
                            >
                              {log.status}
                            </Badge>
                          </li>
                        ))}
                      </ul>
                    )}
                    {callLogs.some((l) => l.error_message) && (
                      <p className="text-xs text-destructive mt-2">
                        {callLogs.find((l) => l.error_message)?.error_message}
                      </p>
                    )}
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      <Dialog open={formOpen} onOpenChange={setFormOpen}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {editId ? "Edit gateway" : "Add Telegram SIP gateway"}
            </DialogTitle>
            <DialogDescription>
              Credentials are stored securely and masked after save. Requires an
              external SIP↔Telegram bridge — not direct Telegram SIP.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label>Name</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} />
            </div>
            <div className="space-y-2">
              <Label>Provider type</Label>
              <Select
                value={providerType}
                onValueChange={(v) => setProviderType(v as GatewayProviderType)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="sip_tg">SIP.TG</SelectItem>
                  <SelectItem value="tg2sip">tg2sip</SelectItem>
                  <SelectItem value="custom">Custom</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex items-center gap-2">
              <Switch checked={isEnabled} onCheckedChange={setIsEnabled} />
              <Label>Enabled</Label>
            </div>
            {(
              [
                ["sip_host", "SIP server / host", "text"],
                ["sip_port", "SIP port", "number"],
                ["sip_username", "SIP username", "text"],
                ["sip_password", "SIP password", "password"],
                ["sip_caller_id", "SIP caller ID", "text"],
                ["telegram_destination_id", "Telegram routing ID", "text"],
                ["gateway_api_base_url", "Gateway API base URL", "text"],
                ["gateway_api_key", "Gateway API key", "password"],
                ["webhook_callback_url", "Webhook callback URL", "text"],
              ] as const
            ).map(([key, label, type]) => (
              <div key={key} className="space-y-2">
                <Label>{label}</Label>
                <Input
                  type={type}
                  value={String(credentials[key] ?? "")}
                  onChange={(e) =>
                    setCredentials((c) => ({
                      ...c,
                      [key]:
                        type === "number"
                          ? Number(e.target.value) || 5060
                          : e.target.value,
                    }))
                  }
                />
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setFormOpen(false)}>
              Cancel
            </Button>
            <Button onClick={onSave} disabled={submitting || !name.trim()}>
              {submitting ? "Saving…" : "Save"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <AlertDialog
        open={!!deleteTarget}
        onOpenChange={(open) => !open && setDeleteTarget(null)}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete gateway?</AlertDialogTitle>
            <AlertDialogDescription>
              This removes &quot;{deleteTarget?.name}&quot; and its call logs.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={onDelete}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
