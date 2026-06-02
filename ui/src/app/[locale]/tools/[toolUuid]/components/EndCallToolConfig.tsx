"use client";

import { useTranslations } from "next-intl";

import type { RecordingResponseSchema } from "@/client/types.gen";
import { RecordingSelect, StaticTextWarning } from "@/components/flow/TextOrAudioInput";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { RadioGroup, RadioGroupItem } from "@/components/ui/radio-group";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";

import { type EndCallMessageType } from "../../config";

export interface EndCallToolConfigProps {
    name: string;
    onNameChange: (name: string) => void;
    description: string;
    onDescriptionChange: (description: string) => void;
    messageType: EndCallMessageType;
    onMessageTypeChange: (messageType: EndCallMessageType) => void;
    customMessage: string;
    onCustomMessageChange: (message: string) => void;
    audioRecordingId: string;
    onAudioRecordingIdChange: (id: string) => void;
    recordings?: RecordingResponseSchema[];
    endCallReason: boolean;
    onEndCallReasonChange: (enabled: boolean) => void;
    endCallReasonDescription: string;
    onEndCallReasonDescriptionChange: (description: string) => void;
}

export function EndCallToolConfig({
    name,
    onNameChange,
    description,
    onDescriptionChange,
    messageType,
    onMessageTypeChange,
    customMessage,
    onCustomMessageChange,
    audioRecordingId,
    onAudioRecordingIdChange,
    recordings = [],
    endCallReason,
    onEndCallReasonChange,
    endCallReasonDescription,
    onEndCallReasonDescriptionChange,
}: EndCallToolConfigProps) {
    const t = useTranslations("components.endCallToolConfig");
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
                    <div className="flex items-center space-x-2">
                        <Switch
                            id="end-call-reason"
                            checked={endCallReason}
                            onCheckedChange={onEndCallReasonChange}
                        />
                        <Label htmlFor="end-call-reason">{t("captureReasonLabel")}</Label>
                    </div>
                    <Label className="text-xs text-muted-foreground">
                        {t("captureReasonHint")}
                    </Label>
                    {endCallReason && (
                        <div className="grid gap-2 pt-2">
                            <Label>{t("reasonDescriptionLabel")}</Label>
                            <Label className="text-xs text-muted-foreground">
                                {t("reasonDescriptionHint")}
                            </Label>
                            <Textarea
                                value={endCallReasonDescription}
                                onChange={(e) => onEndCallReasonDescriptionChange(e.target.value)}
                                placeholder={t("reasonDescriptionPlaceholder")}
                                rows={2}
                            />
                        </div>
                    )}
                </div>

                <div className="grid gap-4 pt-4 border-t">
                    <Label>{t("goodbyeMessageLabel")}</Label>
                    <Label className="text-xs text-muted-foreground">
                        {t("goodbyeMessageHint")}
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
                                <span className="font-medium">{t("audioTitle")}</span>
                                <p className="text-xs text-muted-foreground">
                                    {t("audioDescription")}
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
            </CardContent>
        </Card>
    );
}
