"use client";

import { ExternalLink, FileText } from "lucide-react";
import { useTranslations } from "next-intl";
import { useMemo } from "react";

import type { DocumentResponseSchema } from "@/client/types.gen";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { KNOWLEDGE_BASE_DOC_URL } from "@/constants/documentation";
import { Link } from "@/i18n/navigation";

interface DocumentSelectorProps {
    value: string[];
    onChange: (uuids: string[]) => void;
    documents: DocumentResponseSchema[];
    disabled?: boolean;
    label?: string;
    description?: string;
    showLabel?: boolean;
}

export const DocumentSelector = ({
    value,
    onChange,
    documents,
    disabled = false,
    label,
    description,
    showLabel = true,
}: DocumentSelectorProps) => {
    const t = useTranslations("components.flow.documentSelector");

    const resolvedLabel = label ?? t("defaultLabel");
    const resolvedDescription = description ?? t("defaultDescription");

    // Only show completed documents
    const completedDocuments = useMemo(
        () => documents.filter((doc) => doc.processing_status === "completed"),
        [documents]
    );

    const handleToggle = (documentUuid: string, checked: boolean) => {
        if (checked) {
            onChange([...value, documentUuid]);
        } else {
            onChange(value.filter((uuid) => uuid !== documentUuid));
        }
    };

    const formatFileSize = (bytes: number): string => {
        if (bytes === 0) return `0 ${t("unitBytes")}`;
        const k = 1024;
        const sizes = [t("unitBytes"), "KB", "MB", "GB"];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + " " + sizes[i];
    };

    if (completedDocuments.length === 0) {
        return (
            <div className="space-y-2">
                {showLabel && (
                    <>
                        <Label>{resolvedLabel}</Label>
                        {resolvedDescription && (
                            <Label className="text-xs text-muted-foreground">
                            {resolvedDescription}{" "}
                            <a href={KNOWLEDGE_BASE_DOC_URL} target="_blank" rel="noopener noreferrer" className="underline">{t("learnMore")}</a>
                        </Label>
                        )}
                    </>
                )}
                <div className="border rounded-md p-4 space-y-3">
                    <div className="text-sm text-muted-foreground text-center">
                        {t("emptyState")}
                    </div>
                    <div className="flex justify-center">
                        <Button variant="outline" size="sm" asChild>
                            <Link href="/files" target="_blank">
                                <ExternalLink className="h-4 w-4 mr-2" />
                                {t("uploadDocuments")}
                            </Link>
                        </Button>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="space-y-2">
            {showLabel && (
                <>
                    <Label>{resolvedLabel}</Label>
                    {resolvedDescription && (
                        <Label className="text-xs text-muted-foreground">
                            {resolvedDescription}{" "}
                            <a href={KNOWLEDGE_BASE_DOC_URL} target="_blank" rel="noopener noreferrer" className="underline">{t("learnMore")}</a>
                        </Label>
                    )}
                </>
            )}
            <div className="border rounded-md max-h-[300px] overflow-y-auto">
                <div className="divide-y">
                    {completedDocuments.map((doc) => (
                        <div
                            key={doc.document_uuid}
                            className="flex items-start gap-3 p-3 hover:bg-muted/50 transition-colors"
                        >
                            <Checkbox
                                id={`doc-${doc.document_uuid}`}
                                checked={value.includes(doc.document_uuid)}
                                onCheckedChange={(checked) =>
                                    handleToggle(doc.document_uuid, checked as boolean)
                                }
                                disabled={disabled}
                            />
                            <div className="flex-1 space-y-1">
                                <label
                                    htmlFor={`doc-${doc.document_uuid}`}
                                    className="flex items-center gap-2 cursor-pointer"
                                >
                                    <div className="w-8 h-8 rounded-md bg-blue-500/10 flex items-center justify-center flex-shrink-0">
                                        <FileText className="w-4 h-4 text-blue-500" />
                                    </div>
                                    <div className="flex-1 min-w-0">
                                        <div className="text-sm font-medium truncate">
                                            {doc.filename}
                                        </div>
                                        <div className="text-xs text-muted-foreground">
                                            {formatFileSize(doc.file_size_bytes)} • {doc.retrieval_mode === 'full_document' ? t("fullDocument") : t("chunks", { count: doc.total_chunks })}
                                        </div>
                                    </div>
                                </label>
                            </div>
                        </div>
                    ))}
                </div>
                <div className="p-2 bg-muted/30">
                    <Link
                        href="/files"
                        target="_blank"
                        className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground"
                    >
                        <ExternalLink className="h-4 w-4" />
                        {t("manageDocuments")}
                    </Link>
                </div>
            </div>

            {value.length > 0 && (
                <p className="text-xs text-muted-foreground">
                    {t("selectedCount", { count: value.length })}
                </p>
            )}
        </div>
    );
};
