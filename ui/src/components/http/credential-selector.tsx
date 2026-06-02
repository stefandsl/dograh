"use client";

import { Loader2, PlusIcon } from "lucide-react";
import { useTranslations } from "next-intl";
import { useCallback, useEffect, useState } from "react";

import { listCredentialsApiV1CredentialsGet } from "@/client";
import { CredentialResponse } from "@/client/types.gen";
import { CreateCredentialDialog } from "@/components/http/create-credential-dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { useAuth } from "@/lib/auth";

interface CredentialSelectorProps {
    value: string;
    onChange: (uuid: string) => void;
    disabled?: boolean;
    placeholder?: string;
    label?: string;
    description?: string;
    showLabel?: boolean;
}

export function CredentialSelector({
    value,
    onChange,
    disabled = false,
    placeholder,
    label,
    description,
    showLabel = true,
}: CredentialSelectorProps) {
    const t = useTranslations("components.http.credentialSelector");
    useAuth();

    const resolvedPlaceholder = placeholder ?? t("noAuthentication");
    const resolvedLabel = label ?? t("label");
    const resolvedDescription = description ?? t("description");

    const [credentials, setCredentials] = useState<CredentialResponse[]>([]);
    const [loading, setLoading] = useState(false);
    const [isAddDialogOpen, setIsAddDialogOpen] = useState(false);

    const fetchCredentials = useCallback(async () => {
        setLoading(true);
        try {
            const response = await listCredentialsApiV1CredentialsGet({});
            if (response.error) {
                console.error("Failed to fetch credentials:", response.error);
                setCredentials([]);
                return;
            }
            if (response.data) {
                setCredentials(response.data);
            }
        } catch (error) {
            console.error("Failed to fetch credentials:", error);
            setCredentials([]);
        } finally {
            setLoading(false);
        }
    }, []);

    useEffect(() => {
        fetchCredentials();
    }, [fetchCredentials]);

    const handleCredentialCreated = async (credential: CredentialResponse) => {
        await fetchCredentials();
        onChange(credential.uuid);
    };

    return (
        <div className="grid gap-2">
            {showLabel && (
                <>
                    <Label>{resolvedLabel}</Label>
                    {resolvedDescription && (
                        <Label className="text-xs text-muted-foreground">
                            {resolvedDescription}
                        </Label>
                    )}
                </>
            )}
            <div className="flex gap-2">
                <Select
                    value={value || "none"}
                    onValueChange={(v) => onChange(v === "none" ? "" : v)}
                    disabled={disabled || loading}
                >
                    <SelectTrigger className="flex-1">
                        {loading ? (
                            <div className="flex items-center gap-2">
                                <Loader2 className="h-4 w-4 animate-spin" />
                                <span>{t("loading")}</span>
                            </div>
                        ) : (
                            <SelectValue placeholder={resolvedPlaceholder} />
                        )}
                    </SelectTrigger>
                    <SelectContent>
                        <SelectItem value="none">
                            {resolvedPlaceholder}
                        </SelectItem>
                        {credentials.map((cred) => (
                            <SelectItem key={cred.uuid} value={cred.uuid}>
                                {cred.name} ({cred.credential_type})
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
                <Button
                    variant="outline"
                    size="icon"
                    onClick={() => setIsAddDialogOpen(true)}
                    title={t("addNewCredential")}
                    disabled={disabled}
                >
                    <PlusIcon className="h-4 w-4" />
                </Button>
            </div>

            {credentials.length === 0 && !loading && (
                <div className="p-3 border rounded-md bg-muted/20">
                    <p className="text-sm text-muted-foreground">
                        {t("noCredentialsFound")}
                    </p>
                </div>
            )}

            <CreateCredentialDialog
                open={isAddDialogOpen}
                onOpenChange={setIsAddDialogOpen}
                onCreated={handleCredentialCreated}
            />
        </div>
    );
}
