"use client";

import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";
import { toast } from "sonner";

import {
  createPhoneNumberApiV1OrganizationsTelephonyConfigsConfigIdPhoneNumbersPost,
  getWorkflowsSummaryApiV1WorkflowSummaryGet,
  updatePhoneNumberApiV1OrganizationsTelephonyConfigsConfigIdPhoneNumbersPhoneNumberIdPut,
} from "@/client/sdk.gen";
import type { PhoneNumberResponse } from "@/client/types.gen";
import { Button } from "@/components/ui/button";
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
import { Switch } from "@/components/ui/switch";
import { detailFromError } from "@/lib/apiError";
import { useAuth } from "@/lib/auth";

interface PhoneNumberDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  configId: number;
  existing?: PhoneNumberResponse | null;
  onSaved: () => void;
}

const NO_WORKFLOW = "__none__";

// Mirrors api/schemas/telephony_phone_number.py::_validate_address_shape and
// api/utils/telephony_address.py — keep in sync. Returns an error message
// when the address would normalize to a broken canonical form, or null when
// the input is acceptable.
const ADDRESS_FORMAT_STRIP_RE = /[\s\-()]/g;
const ADDRESS_E164_RE = /^\+\d{8,15}$/;
const ADDRESS_BARE_DIGITS_RE = /^\d{8,15}$/;

// Returns an error message key, or null when the input is acceptable.
function validateAddress(rawAddress: string, countryCode: string): string | null {
  const trimmed = rawAddress.trim();
  if (!trimmed) return "addressRequired";
  if (/^sips?:/i.test(trimmed)) return null;
  const stripped = trimmed.replace(ADDRESS_FORMAT_STRIP_RE, "");
  if (ADDRESS_E164_RE.test(stripped)) return null;
  if (ADDRESS_BARE_DIGITS_RE.test(stripped) && !countryCode.trim()) {
    return "addressPstnNeedsCountry";
  }
  return null;
}

export function PhoneNumberDialog({
  open,
  onOpenChange,
  configId,
  existing,
  onSaved,
}: PhoneNumberDialogProps) {
  const t = useTranslations("components.telephony.phoneNumberDialog");
  const { user, getAccessToken } = useAuth();
  const isEdit = !!existing;

  const [address, setAddress] = useState("");
  const [countryCode, setCountryCode] = useState("");
  const [label, setLabel] = useState("");
  const [isActive, setIsActive] = useState(true);
  const [isDefaultCallerId, setIsDefaultCallerId] = useState(false);
  const [inboundWorkflowId, setInboundWorkflowId] = useState<string>(NO_WORKFLOW);
  const [workflows, setWorkflows] = useState<{ id: number; name: string }[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [addressTouched, setAddressTouched] = useState(false);

  // Reset form when the dialog opens.
  useEffect(() => {
    if (!open) return;
    setAddress(existing?.address ?? "");
    setCountryCode(existing?.country_code ?? "");
    setLabel(existing?.label ?? "");
    setIsActive(existing?.is_active ?? true);
    setIsDefaultCallerId(existing?.is_default_caller_id ?? false);
    setInboundWorkflowId(
      existing?.inbound_workflow_id ? String(existing.inbound_workflow_id) : NO_WORKFLOW,
    );
    setAddressTouched(false);
  }, [open, existing]);

  // Only validate the address on create — edits keep the immutable address.
  const addressErrorKey = isEdit ? null : validateAddress(address, countryCode);
  const addressError = addressErrorKey ? t(addressErrorKey) : null;

  // Load workflows for the inbound dropdown.
  useEffect(() => {
    if (!open || !user) return;
    let cancelled = false;
    (async () => {
      const token = await getAccessToken();
      const res = await getWorkflowsSummaryApiV1WorkflowSummaryGet({
        headers: { Authorization: `Bearer ${token}` },
        query: { status: "active" },
      });
      if (cancelled) return;
      const items = res.data ?? [];
      setWorkflows(items.map((w) => ({ id: w.id, name: w.name })));
    })();
    return () => {
      cancelled = true;
    };
  }, [open, user, getAccessToken]);

  const handleSubmit = async () => {
    if (!isEdit) {
      const errKey = validateAddress(address, countryCode);
      if (errKey) {
        setAddressTouched(true);
        toast.error(t(errKey));
        return;
      }
    }
    setSubmitting(true);
    try {
      const token = await getAccessToken();
      const inboundId =
        inboundWorkflowId === NO_WORKFLOW ? null : Number(inboundWorkflowId);

      let providerSync: PhoneNumberResponse["provider_sync"] | undefined;
      if (isEdit && existing) {
        const res = await updatePhoneNumberApiV1OrganizationsTelephonyConfigsConfigIdPhoneNumbersPhoneNumberIdPut(
          {
            headers: { Authorization: `Bearer ${token}` },
            path: { config_id: configId, phone_number_id: existing.id },
            body: {
              label: label || undefined,
              is_active: isActive,
              country_code: countryCode || undefined,
              inbound_workflow_id: inboundId ?? undefined,
              clear_inbound_workflow: inboundId === null,
            },
          },
        );
        if (res.error) throw new Error(detailFromError(res.error, t("saveError")));
        providerSync = res.data?.provider_sync;
        toast.success(t("toastUpdated"));
      } else {
        const res = await createPhoneNumberApiV1OrganizationsTelephonyConfigsConfigIdPhoneNumbersPost(
          {
            headers: { Authorization: `Bearer ${token}` },
            path: { config_id: configId },
            body: {
              address: address.trim(),
              country_code: countryCode || undefined,
              label: label || undefined,
              is_active: isActive,
              is_default_caller_id: isDefaultCallerId,
              inbound_workflow_id: inboundId ?? undefined,
            },
          },
        );
        if (res.error) throw new Error(detailFromError(res.error, t("saveError")));
        providerSync = res.data?.provider_sync;
        toast.success(t("toastAdded"));
      }
      if (providerSync && !providerSync.ok) {
        toast.warning(providerSync.message ?? t("toastSyncWarning"));
      }
      onOpenChange(false);
      onSaved();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : t("saveError"));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>
            {isEdit ? t("titleEdit") : t("titleAdd")}
          </DialogTitle>
          <DialogDescription>
            {t("description")}
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1">
            <Label htmlFor="pn-address">{t("addressLabel")}</Label>
            <Input
              id="pn-address"
              placeholder={t("addressPlaceholder")}
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              onBlur={() => setAddressTouched(true)}
              disabled={isEdit}
              aria-invalid={addressTouched && !!addressError}
            />
            {!isEdit && addressTouched && addressError && (
              <p className="text-xs text-destructive">{addressError}</p>
            )}
            {isEdit && (
              <p className="text-xs text-muted-foreground">
                {t("addressImmutable")}
              </p>
            )}
            {isEdit && (
              <p className="text-xs text-muted-foreground">
                {t.rich("addressStoredAs", {
                  normalized: existing?.address_normalized ?? "",
                  type: existing?.address_type ?? "",
                  code: (c) => <code>{c}</code>,
                })}
              </p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1">
              <Label htmlFor="pn-country">{t("countryLabel")}</Label>
              <Input
                id="pn-country"
                placeholder={t("countryPlaceholder")}
                maxLength={2}
                value={countryCode}
                onChange={(e) => setCountryCode(e.target.value.toUpperCase())}
              />
            </div>
            <div className="space-y-1">
              <Label htmlFor="pn-label">{t("labelLabel")}</Label>
              <Input
                id="pn-label"
                placeholder={t("labelPlaceholder")}
                value={label}
                onChange={(e) => setLabel(e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-1">
            <Label htmlFor="pn-workflow">{t("inboundWorkflowLabel")}</Label>
            <Select value={inboundWorkflowId} onValueChange={setInboundWorkflowId}>
              <SelectTrigger id="pn-workflow">
                <SelectValue placeholder={t("noneOption")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NO_WORKFLOW}>{t("noneOption")}</SelectItem>
                {workflows.map((w) => (
                  <SelectItem key={w.id} value={String(w.id)}>
                    #{w.id} - {w.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              {t("inboundWorkflowHint")}
            </p>
          </div>

          <div className="flex items-center justify-between rounded border p-3">
            <Label className="text-sm">{t("activeLabel")}</Label>
            <Switch checked={isActive} onCheckedChange={setIsActive} />
          </div>

          {!isEdit && (
            <div className="flex items-center justify-between rounded border p-3">
              <div>
                <Label className="text-sm">{t("defaultCallerIdLabel")}</Label>
                <p className="text-xs text-muted-foreground">
                  {t("defaultCallerIdHint")}
                </p>
              </div>
              <Switch
                checked={isDefaultCallerId}
                onCheckedChange={setIsDefaultCallerId}
              />
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
            {t("cancel")}
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={submitting || (!isEdit && !!addressError)}
          >
            {submitting ? t("saving") : isEdit ? t("saveChanges") : t("add")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
