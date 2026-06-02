"use client";

import { useTranslations } from "next-intl";

import type { RecordingResponseSchema } from "@/client/types.gen";
import { StaticTextWarning, TextOrAudioInput } from "@/components/flow/TextOrAudioInput";
import {
    CredentialSelector,
    type HttpMethod,
    HttpMethodSelector,
    KeyValueEditor,
    type KeyValueItem,
    ParameterEditor,
    PresetParameterEditor,
    type PresetToolParameter,
    type ToolParameter,
    UrlInput,
} from "@/components/http";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";

export interface HttpApiToolConfigProps {
    name: string;
    onNameChange: (name: string) => void;
    description: string;
    onDescriptionChange: (description: string) => void;
    httpMethod: HttpMethod;
    onHttpMethodChange: (method: HttpMethod) => void;
    url: string;
    onUrlChange: (url: string) => void;
    credentialUuid: string;
    onCredentialUuidChange: (uuid: string) => void;
    headers: KeyValueItem[];
    onHeadersChange: (headers: KeyValueItem[]) => void;
    parameters: ToolParameter[];
    onParametersChange: (parameters: ToolParameter[]) => void;
    presetParameters: PresetToolParameter[];
    onPresetParametersChange: (parameters: PresetToolParameter[]) => void;
    timeoutMs: number;
    onTimeoutMsChange: (timeout: number) => void;
    customMessage: string;
    onCustomMessageChange: (message: string) => void;
    customMessageType: 'text' | 'audio';
    onCustomMessageTypeChange: (type: 'text' | 'audio') => void;
    customMessageRecordingId: string;
    onCustomMessageRecordingIdChange: (id: string) => void;
    recordings?: RecordingResponseSchema[];
}

export function HttpApiToolConfig({
    name,
    onNameChange,
    description,
    onDescriptionChange,
    httpMethod,
    onHttpMethodChange,
    url,
    onUrlChange,
    credentialUuid,
    onCredentialUuidChange,
    headers,
    onHeadersChange,
    parameters,
    onParametersChange,
    presetParameters,
    onPresetParametersChange,
    timeoutMs,
    onTimeoutMsChange,
    customMessage,
    onCustomMessageChange,
    customMessageType,
    onCustomMessageTypeChange,
    customMessageRecordingId,
    onCustomMessageRecordingIdChange,
    recordings = [],
}: HttpApiToolConfigProps) {
    const t = useTranslations("components.httpApiToolConfig");
    const tb = useTranslations("brand");
    return (
        <Card>
            <CardHeader>
                <CardTitle>{t("title")}</CardTitle>
                <CardDescription>
                    {t("description")}
                </CardDescription>
            </CardHeader>
            <CardContent>
                <Tabs defaultValue="settings" className="w-full">
                    <TabsList className="grid w-full grid-cols-3">
                        <TabsTrigger value="settings">{t("tabSettings")}</TabsTrigger>
                        <TabsTrigger value="auth">{t("tabAuthentication")}</TabsTrigger>
                        <TabsTrigger value="parameters">{t("tabParameters")}</TabsTrigger>
                    </TabsList>

                    <TabsContent value="settings" className="space-y-4 mt-4">
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

                        <div className="grid grid-cols-2 gap-4">
                            <div className="grid gap-2">
                                <Label>{t("httpMethodLabel")}</Label>
                                <HttpMethodSelector
                                    value={httpMethod}
                                    onChange={onHttpMethodChange}
                                />
                            </div>
                            <div className="grid gap-2">
                                <Label>{t("timeoutLabel")}</Label>
                                <Input
                                    type="number"
                                    value={timeoutMs}
                                    onChange={(e) =>
                                        onTimeoutMsChange(parseInt(e.target.value) || 5000)
                                    }
                                    min={1000}
                                    max={30000}
                                />
                            </div>
                        </div>

                        <div className="grid gap-2">
                            <Label>{t("endpointUrlLabel")}</Label>
                            <UrlInput
                                value={url}
                                onChange={onUrlChange}
                                placeholder="https://api.example.com/appointments"
                                showValidation
                            />
                        </div>

                        <div className="grid gap-2 pt-4 border-t">
                            <Label>{t("customMessageLabel")}</Label>
                            <Label className="text-xs text-muted-foreground">
                                {t("customMessageHint")}
                            </Label>
                            <TextOrAudioInput
                                type={customMessageType}
                                onTypeChange={onCustomMessageTypeChange}
                                recordingId={customMessageRecordingId}
                                onRecordingIdChange={onCustomMessageRecordingIdChange}
                                recordings={recordings}
                            >
                                <>
                                    <StaticTextWarning />
                                    <Textarea
                                        value={customMessage}
                                        onChange={(e) => onCustomMessageChange(e.target.value)}
                                        placeholder={t("customMessagePlaceholder")}
                                        rows={2}
                                    />
                                </>
                            </TextOrAudioInput>
                        </div>
                    </TabsContent>

                    <TabsContent value="auth" className="space-y-4 mt-4">
                        <CredentialSelector
                            value={credentialUuid}
                            onChange={onCredentialUuidChange}
                        />
                    </TabsContent>

                    <TabsContent value="parameters" className="space-y-4 mt-4">
                        <div className="grid gap-2">
                            <Label>{t("llmParametersLabel")}</Label>
                            <Label className="text-xs text-muted-foreground">
                                {t("llmParametersHint")}
                            </Label>
                            <ParameterEditor
                                parameters={parameters}
                                onChange={onParametersChange}
                            />
                        </div>

                        <div className="grid gap-2 pt-4 border-t">
                            <Label>{t("presetParametersLabel")}</Label>
                            <Label className="text-xs text-muted-foreground">
                                {t("presetParametersHint", { brand: tb("name"), template: "{{initial_context.phone_number}}" })}
                            </Label>
                            <PresetParameterEditor
                                parameters={presetParameters}
                                onChange={onPresetParametersChange}
                            />
                        </div>

                        <div className="grid gap-2 pt-4 border-t">
                            <Label>{t("customHeadersLabel")}</Label>
                            <Label className="text-xs text-muted-foreground">
                                {t("customHeadersHint")}
                            </Label>
                            <KeyValueEditor
                                items={headers}
                                onChange={onHeadersChange}
                                keyPlaceholder={t("headerNamePlaceholder")}
                                valuePlaceholder={t("headerValuePlaceholder")}
                                addButtonText={t("addHeaderButton")}
                            />
                        </div>
                    </TabsContent>
                </Tabs>
            </CardContent>
        </Card>
    );
}
