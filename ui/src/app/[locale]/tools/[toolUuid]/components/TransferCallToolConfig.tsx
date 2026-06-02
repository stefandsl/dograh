"use client";

import { useTranslations } from "next-intl";
import {useState } from "react";

import type { RecordingResponseSchema } from "@/client/types.gen";
import { RecordingSelect, StaticTextWarning } from "@/components/flow/TextOrAudioInput";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Textarea } from "@/components/ui/textarea";

import { type EndCallMessageType } from "../../config";

export interface TransferCallToolConfigProps {
    name: string;
    onNameChange: (name: string) => void;
    description: string;
    onDescriptionChange: (description: string) => void;
    destination: string;
    onDestinationChange: (destination: string) => void;
    messageType: EndCallMessageType;
    onMessageTypeChange: (messageType: EndCallMessageType) => void;
    customMessage: string;
    onCustomMessageChange: (message: string) => void;
    audioRecordingId: string;
    onAudioRecordingIdChange: (id: string) => void;
    recordings?: RecordingResponseSchema[];
    timeout?: number;  // Make optional to match API type
    onTimeoutChange: (timeout: number) => void;
}

export function TransferCallToolConfig({
    name,
    onNameChange,
    description,
    onDescriptionChange,
    destination,
    onDestinationChange,
    messageType,
    onMessageTypeChange,
    customMessage,
    onCustomMessageChange,
    audioRecordingId,
    onAudioRecordingIdChange,
    recordings = [],
    timeout,
    onTimeoutChange,
}: TransferCallToolConfigProps) {
    const t = useTranslations("components.transferCallToolConfig");
    const [sipMode, setSipMode] = useState(() => /^(PJSIP|SIP)\//i.test(destination));

    // Validation patterns
    const isValidPhoneNumber = (phone: string): boolean => {
        const e164Pattern = /^\+[1-9]\d{1,14}$/;
        return e164Pattern.test(phone);
    };

    const isValidSipEndpoint = (endpoint: string): boolean => {
        const sipPattern = /^(PJSIP|SIP)\/[\w\-\.@]+$/i;
        return sipPattern.test(endpoint);
    };

    const getValidationError = (): string | null => {
        if (!destination) return null;

        if (sipMode) {
            return isValidSipEndpoint(destination)
                ? null
                : t("sipValidationError");
        } else {
            return isValidPhoneNumber(destination)
                ? null
                : t("phoneValidationError");
        }
    };

    const destinationError = getValidationError();

    const handleSipModeToggle = () => {
        setSipMode(!sipMode);
        onDestinationChange(""); // Clear destination when switching modes
    };

    return (
        <Card>
            <CardHeader>
                <CardTitle>{t("title")}</CardTitle>
                <CardDescription>
                    {t("cardDescription")}
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
                <div className="grid gap-2">
                    <Label>{t("toolNameLabel")}</Label>
                    <Label className="text-xs text-muted-foreground">
                        {t("toolNameHint")}
                    </Label>
                    <Input
                        value={name}
                        onChange={(e) => onNameChange(e.target.value)}
                        placeholder={t("toolNamePlaceholder")}
                    />
                </div>

                <div className="grid gap-2">
                    <Label>{t("descriptionLabel")}</Label>
                    <Label className="text-xs text-muted-foreground">
                        {t("descriptionHint")}
                    </Label>
                    <Textarea
                        value={description}
                        onChange={(e) => onDescriptionChange(e.target.value)}
                        placeholder={t("descriptionPlaceholder")}
                        rows={3}
                    />
                </div>

                <div className="grid gap-2 pt-4 border-t">
                    <Label>{t("destinationLabel")}</Label>
                    <Label className="text-xs text-muted-foreground">
                        {sipMode
                            ? t("destinationHintSip")
                            : t("destinationHintPhone")
                        }
                    </Label>
                    <Input
                        value={destination}
                        onChange={(e) => onDestinationChange(e.target.value)}
                        placeholder={sipMode ? t("destinationPlaceholderSip") : t("destinationPlaceholderPhone")}
                        className={destinationError ? "border-red-500 focus:border-red-500" : ""}
                    />
                    {destinationError && (
                        <Label className="text-xs text-red-500">
                            {destinationError}
                        </Label>
                    )}
                    <button
                        type="button"
                        className="text-xs text-muted-foreground hover:text-foreground underline w-fit"
                        onClick={handleSipModeToggle}
                    >
                        {sipMode ? t("usePhoneInstead") : t("useSipInstead")}
                    </button>
                </div>

                <div className="grid gap-4 pt-4 border-t">
                    <Label>{t("preTransferMessageLabel")}</Label>
                    <Label className="text-xs text-muted-foreground">
                        {t("preTransferMessageHint")}
                    </Label>
                    <RadioGroup
                        value={messageType}
                        onValueChange={(v) => onMessageTypeChange(v as EndCallMessageType)}
                        className="space-y-3"
                    >
                        <label
                            htmlFor="none"
                            className="flex items-center space-x-3 p-3 border rounded-lg hover:bg-muted/50 cursor-pointer"
                        >
                            <RadioGroupItem value="none" id="none" />
                            <div className="flex-1">
                                <span className="font-medium">{t("noMessageTitle")}</span>
                                <p className="text-xs text-muted-foreground">
                                    {t("noMessageDescription")}
                                </p>
                            </div>
                        </label>
                        <div className="flex items-start space-x-3 p-3 border rounded-lg hover:bg-muted/50">
                            <RadioGroupItem value="custom" id="custom" className="mt-1" />
                            <label htmlFor="custom" className="flex-1 space-y-2 cursor-pointer">
                                <span className="font-medium">{t("customMessageTitle")}</span>
                                <p className="text-xs text-muted-foreground">
                                    {t("customMessageDescription")}
                                </p>
                            </label>
                        </div>
                        {messageType === "custom" && (
                            <div className="pl-8 space-y-2">
                                <StaticTextWarning />
                                <Textarea
                                    value={customMessage}
                                    onChange={(e) => onCustomMessageChange(e.target.value)}
                                    placeholder={t("customMessagePlaceholder")}
                                    rows={2}
                                />
                            </div>
                        )}
                        <div className="flex items-start space-x-3 p-3 border rounded-lg hover:bg-muted/50">
                            <RadioGroupItem value="audio" id="audio" className="mt-1" />
                            <label htmlFor="audio" className="flex-1 space-y-2 cursor-pointer">
                                <span className="font-medium">{t("audioMessageTitle")}</span>
                                <p className="text-xs text-muted-foreground">
                                    {t("audioMessageDescription")}
                                </p>
                            </label>
                        </div>
                        {messageType === "audio" && (
                            <div className="pl-8">
                                <RecordingSelect
                                    value={audioRecordingId}
                                    onChange={onAudioRecordingIdChange}
                                    recordings={recordings}
                                />
                            </div>
                        )}
                    </RadioGroup>
                </div>

                <div className="grid gap-2 pt-4 border-t">
                    <Label>{t("timeoutLabel")}</Label>
                    <Label className="text-xs text-muted-foreground">
                        {t("timeoutHint")}
                    </Label>
                    <Input
                        type="number"
                        value={timeout ?? 30}
                        onChange={(e) => {
                            const value = parseInt(e.target.value) || 30;
                            // Clamp value between 5 and 120 seconds
                            const clampedValue = Math.min(Math.max(value, 5), 120);
                            onTimeoutChange(clampedValue);
                        }}
                        placeholder="30"
                        min="5"
                        max="120"
                        className="w-32"
                    />
                    <Label className="text-xs text-muted-foreground">
                        {t("timeoutDefault")}
                    </Label>
                </div>
            </CardContent>
        </Card>
    );
}
