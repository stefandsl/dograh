"use client";

import { format } from "date-fns";
import { ArrowLeft, BookA, Brain, CalendarIcon, Clipboard, Download, ExternalLink, FileDown, Fingerprint, Loader2, Mic, Pause, PhoneOff, Play, Rocket, Settings, Trash2Icon, Upload, Variable, X } from "lucide-react";
import { useParams, useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";

import {
    downloadWorkflowReportApiV1WorkflowWorkflowIdReportGet,
    getAmbientNoiseUploadUrlApiV1WorkflowAmbientNoiseUploadUrlPost,
    getModelConfigurationV2ApiV1OrganizationsModelConfigurationsV2Get,
    getModelConfigurationV2DefaultsApiV1OrganizationsModelConfigurationsV2DefaultsGet,
    getWorkflowApiV1WorkflowFetchWorkflowIdGet,
} from "@/client/sdk.gen";
import type {
    OrganizationAiModelConfigurationResponse,
    OrganizationAiModelConfigurationV2,
    WorkflowResponse,
} from "@/client/types.gen";
import {
    AIModelConfigurationV2Editor,
    type ModelConfigurationDefaultsV2,
} from "@/components/AIModelConfigurationV2Editor";
import { FlowEdge, FlowNode } from "@/components/flow/types";
import { LLMConfigSelector } from "@/components/LLMConfigSelector";
import { ServiceConfigurationForm } from "@/components/ServiceConfigurationForm";
import SpinLoader from "@/components/SpinLoader";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { SETTINGS_DOCUMENTATION_URLS } from "@/constants/documentation";
import { UnsavedChangesProvider, useUnsavedChanges, useUnsavedChangesContext } from "@/context/UnsavedChangesContext";
import { useAudioPlayback } from "@/hooks/useAudioPlayback";
import { Link } from "@/i18n/navigation";
import { detailFromError } from "@/lib/apiError";
import { useAuth } from "@/lib/auth";
import logger from "@/lib/logger";
import {
    type AmbientNoiseConfiguration,
    DEFAULT_VOICEMAIL_DETECTION_CONFIGURATION,
    DEFAULT_WORKFLOW_CONFIGURATIONS,
    type TurnStopStrategy,
    type VoicemailDetectionConfiguration,
    type WorkflowConfigurations,
} from "@/types/workflow-configurations";

import { EmbedDialog } from "../components/EmbedDialog";
import { useWorkflowState } from "../hooks/useWorkflowState";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const DEFAULT_AMBIENT_NOISE_CONFIG: AmbientNoiseConfiguration = {
    enabled: false,
    volume: 0.3,
};

const DEFAULT_VOICEMAIL_SYSTEM_PROMPT = `You are a voicemail detection classifier for an OUTBOUND calling system. A bot has called a phone number and you need to determine if a human answered or if the call went to voicemail based on the provided text.

HUMAN ANSWERED - LIVE CONVERSATION (respond "CONVERSATION"):
- Personal greetings: "Hello?", "Hi", "Yeah?", "John speaking"
- Interactive responses: "Who is this?", "What do you want?", "Can I help you?"
- Conversational tone expecting back-and-forth dialogue
- Questions directed at the caller: "Hello? Anyone there?"
- Informal responses: "Yep", "What's up?", "Speaking"
- Natural, spontaneous speech patterns
- Immediate acknowledgment of the call

VOICEMAIL SYSTEM (respond "VOICEMAIL"):
- Automated voicemail greetings: "Hi, you've reached [name], please leave a message"
- Phone carrier messages: "The number you have dialed is not in service", "Please leave a message", "All circuits are busy"
- Professional voicemail: "This is [name], I'm not available right now"
- Instructions about leaving messages: "leave a message", "leave your name and number"
- References to callback or messaging: "call me back", "I'll get back to you"
- Carrier system messages: "mailbox is full", "has not been set up"
- Business hours messages: "our office is currently closed"

Respond with ONLY "CONVERSATION" if a person answered, or "VOICEMAIL" if it's voicemail/recording.`;

// Sidebar navigation items
const NAV_ITEMS = [
    { id: "general", labelKey: "navGeneral", icon: Settings },
    { id: "models", labelKey: "navModelOverrides", icon: Brain },
    { id: "variables", labelKey: "navTemplateVariables", icon: Variable },
    { id: "dictionary", labelKey: "navDictionary", icon: BookA },
    { id: "voicemail", labelKey: "navVoicemailDetection", icon: PhoneOff },
    { id: "recordings", labelKey: "navRecordings", icon: Mic },
    { id: "deployment", labelKey: "navAddToWebsite", icon: Rocket },
    { id: "report", labelKey: "navReport", icon: FileDown },
    { id: "identity", labelKey: "navAgentUuid", icon: Fingerprint },
];

// ---------------------------------------------------------------------------
// Section: Report
// ---------------------------------------------------------------------------

function ReportSection({ workflowId }: { workflowId: number }) {
    const t = useTranslations("pages.workflow.workflowId.settings");
    const [startDate, setStartDate] = useState<Date | undefined>(undefined);
    const [startTime, setStartTime] = useState("00:00");
    const [endDate, setEndDate] = useState<Date | undefined>(undefined);
    const [endTime, setEndTime] = useState("23:59");
    const [isPopoverOpen, setIsPopoverOpen] = useState(false);
    const [isDownloading, setIsDownloading] = useState(false);

    const buildDateTime = (date: Date | undefined, time: string): string | undefined => {
        if (!date) return undefined;
        const [hours, minutes] = time.split(":").map(Number);
        const combined = new Date(date);
        combined.setHours(hours, minutes, 0, 0);
        return combined.toISOString();
    };

    const handleDownload = async () => {
        setIsDownloading(true);
        setIsPopoverOpen(false);
        try {
            const response = await downloadWorkflowReportApiV1WorkflowWorkflowIdReportGet({
                path: { workflow_id: workflowId },
                query: {
                    start_date: buildDateTime(startDate, startTime),
                    end_date: buildDateTime(endDate, endTime),
                },
                parseAs: "blob",
            });

            if (response.data) {
                const blob = response.data as Blob;
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement("a");
                a.href = url;
                a.download = `workflow_${workflowId}_report.csv`;
                document.body.appendChild(a);
                a.click();
                a.remove();
                window.URL.revokeObjectURL(url);
            } else {
                toast.error(t("reportDownloadError"));
            }
        } catch (err) {
            logger.error(`Failed to download workflow report: ${err}`);
            toast.error(t("reportDownloadError"));
        } finally {
            setIsDownloading(false);
        }
    };

    const handleClear = () => {
        setStartDate(undefined);
        setStartTime("00:00");
        setEndDate(undefined);
        setEndTime("23:59");
    };

    return (
        <Card id="report">
            <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                    <FileDown className="h-4 w-4" />
                    {t("reportTitle")}
                </CardTitle>
                <CardDescription>
                    {t("reportDescription")}
                </CardDescription>
            </CardHeader>
            <CardFooter className="border-t pt-6">
                <Popover open={isPopoverOpen} onOpenChange={setIsPopoverOpen}>
                    <PopoverTrigger asChild>
                        <Button variant="outline" disabled={isDownloading}>
                            <Download className="h-4 w-4 mr-2" />
                            {t("reportDownloadButton")}
                        </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-4" align="start">
                        <div className="space-y-4">
                            <div className="text-sm font-medium">{t("reportFilterByDateRange")}</div>
                            <div className="grid gap-3">
                                <div className="space-y-1.5">
                                    <Label className="text-xs">{t("reportFrom")}</Label>
                                    <div className="flex gap-2">
                                        <Popover>
                                            <PopoverTrigger asChild>
                                                <Button variant="outline" size="sm" className="w-[140px] justify-start text-left font-normal">
                                                    <CalendarIcon className="mr-2 h-3.5 w-3.5" />
                                                    {startDate ? format(startDate, "MMM dd, yyyy") : t("reportStartDate")}
                                                </Button>
                                            </PopoverTrigger>
                                            <PopoverContent className="w-auto p-0" align="start">
                                                <Calendar
                                                    mode="single"
                                                    selected={startDate}
                                                    onSelect={setStartDate}
                                                    disabled={(date) => (endDate ? date > endDate : false)}
                                                />
                                            </PopoverContent>
                                        </Popover>
                                        <Input
                                            type="time"
                                            value={startTime}
                                            onChange={(e) => setStartTime(e.target.value)}
                                            className="w-[100px] h-8 text-xs"
                                        />
                                    </div>
                                </div>
                                <div className="space-y-1.5">
                                    <Label className="text-xs">{t("reportTo")}</Label>
                                    <div className="flex gap-2">
                                        <Popover>
                                            <PopoverTrigger asChild>
                                                <Button variant="outline" size="sm" className="w-[140px] justify-start text-left font-normal">
                                                    <CalendarIcon className="mr-2 h-3.5 w-3.5" />
                                                    {endDate ? format(endDate, "MMM dd, yyyy") : t("reportEndDate")}
                                                </Button>
                                            </PopoverTrigger>
                                            <PopoverContent className="w-auto p-0" align="start">
                                                <Calendar
                                                    mode="single"
                                                    selected={endDate}
                                                    onSelect={setEndDate}
                                                    disabled={(date) => (startDate ? date < startDate : false)}
                                                />
                                            </PopoverContent>
                                        </Popover>
                                        <Input
                                            type="time"
                                            value={endTime}
                                            onChange={(e) => setEndTime(e.target.value)}
                                            className="w-[100px] h-8 text-xs"
                                        />
                                    </div>
                                </div>
                            </div>
                            <Separator />
                            <div className="flex justify-between">
                                <Button variant="ghost" size="sm" onClick={handleClear}>
                                    {t("reportClear")}
                                </Button>
                                <Button size="sm" onClick={handleDownload} disabled={isDownloading}>
                                    <Download className="h-3.5 w-3.5 mr-1.5" />
                                    {startDate || endDate ? t("reportDownloadFiltered") : t("reportDownloadAll")}
                                </Button>
                            </div>
                        </div>
                    </PopoverContent>
                </Popover>
            </CardFooter>
        </Card>
    );
}

// ---------------------------------------------------------------------------
// Section: General
// ---------------------------------------------------------------------------

const MAX_AMBIENT_NOISE_FILE_SIZE = 10 * 1024 * 1024; // 10MB

function GeneralSection({
    workflowConfigurations,
    workflowName,
    workflowId,
    onSave,
}: {
    workflowConfigurations: WorkflowConfigurations;
    workflowName: string;
    workflowId: number;
    onSave: (configurations: WorkflowConfigurations, workflowName: string) => Promise<void>;
}) {
    const t = useTranslations("pages.workflow.workflowId.settings");
    const [name, setName] = useState(workflowName);
    const [ambientNoiseConfig, setAmbientNoiseConfig] = useState<AmbientNoiseConfiguration>(
        workflowConfigurations.ambient_noise_configuration || DEFAULT_AMBIENT_NOISE_CONFIG,
    );
    const [maxCallDuration, setMaxCallDuration] = useState(workflowConfigurations.max_call_duration || 600);
    const [maxUserIdleTimeout, setMaxUserIdleTimeout] = useState(workflowConfigurations.max_user_idle_timeout || 10);
    const [smartTurnStopSecs, setSmartTurnStopSecs] = useState(workflowConfigurations.smart_turn_stop_secs || 2);
    const [turnStopStrategy, setTurnStopStrategy] = useState<TurnStopStrategy>(
        workflowConfigurations.turn_stop_strategy || "transcription",
    );
    const [contextCompactionEnabled, setContextCompactionEnabled] = useState(
        workflowConfigurations.context_compaction_enabled ?? false,
    );
    const [isSaving, setIsSaving] = useState(false);
    const [isUploadingAudio, setIsUploadingAudio] = useState(false);
    const [audioUploadError, setAudioUploadError] = useState<string | null>(null);
    const ambientFileInputRef = useRef<HTMLInputElement>(null);
    const { playingId, toggle: togglePlayback } = useAudioPlayback();

    const isDirty = useMemo(() => {
        const initAmbient = workflowConfigurations.ambient_noise_configuration || DEFAULT_AMBIENT_NOISE_CONFIG;
        return (
            name !== workflowName ||
            JSON.stringify(ambientNoiseConfig) !== JSON.stringify(initAmbient) ||
            maxCallDuration !== (workflowConfigurations.max_call_duration || 600) ||
            maxUserIdleTimeout !== (workflowConfigurations.max_user_idle_timeout || 10) ||
            smartTurnStopSecs !== (workflowConfigurations.smart_turn_stop_secs || 2) ||
            turnStopStrategy !== (workflowConfigurations.turn_stop_strategy || "transcription") ||
            contextCompactionEnabled !== (workflowConfigurations.context_compaction_enabled ?? false)
        );
    }, [name, workflowName, ambientNoiseConfig, maxCallDuration, maxUserIdleTimeout, smartTurnStopSecs, turnStopStrategy, contextCompactionEnabled, workflowConfigurations]);

    useUnsavedChanges("general", isDirty);

    const handleAmbientFileUpload = async (file: File) => {
        if (file.size > MAX_AMBIENT_NOISE_FILE_SIZE) {
            setAudioUploadError(t("ambientFileTooLarge", { size: (file.size / (1024 * 1024)).toFixed(1) }));
            return;
        }

        setIsUploadingAudio(true);
        setAudioUploadError(null);

        try {
            // 1. Get presigned upload URL
            const res = await getAmbientNoiseUploadUrlApiV1WorkflowAmbientNoiseUploadUrlPost({
                body: {
                    workflow_id: Number(workflowId),
                    filename: file.name,
                    mime_type: file.type || "audio/wav",
                    file_size: file.size,
                },
            });

            if (res.error || !res.data?.upload_url) {
                throw new Error(t("ambientGetUploadUrlError"));
            }

            const data = res.data;

            // 2. Upload file to storage
            const uploadRes = await fetch(data.upload_url, {
                method: "PUT",
                body: file,
                headers: { "Content-Type": file.type || "audio/wav" },
            });
            if (!uploadRes.ok) {
                throw new Error(t("ambientFileUploadFailed"));
            }

            // 3. Update config with storage reference
            setAmbientNoiseConfig((prev) => ({
                ...prev,
                storage_key: data.storage_key,
                storage_backend: data.storage_backend,
                original_filename: file.name,
            }));
        } catch (err) {
            setAudioUploadError(err instanceof Error ? err.message : t("ambientUploadFailed"));
        } finally {
            setIsUploadingAudio(false);
            if (ambientFileInputRef.current) ambientFileInputRef.current.value = "";
        }
    };

    const handleRemoveCustomAudio = () => {
        setAmbientNoiseConfig((prev) => ({
            enabled: prev.enabled,
            volume: prev.volume,
        }));
    };

    const handleSave = async () => {
        setIsSaving(true);
        try {
            await onSave(
                {
                    ...workflowConfigurations,
                    ambient_noise_configuration: ambientNoiseConfig,
                    max_call_duration: maxCallDuration,
                    max_user_idle_timeout: maxUserIdleTimeout,
                    smart_turn_stop_secs: smartTurnStopSecs,
                    turn_stop_strategy: turnStopStrategy,
                    context_compaction_enabled: contextCompactionEnabled,
                },
                name,
            );
        } catch (error) {
            console.error("Failed to save general settings:", error);
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <Card id="general">
            <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                    <Settings className="h-4 w-4" />
                    {t("generalTitle")}
                </CardTitle>
                <CardDescription>{t("generalDescription")}{" "}
                    <a href={SETTINGS_DOCUMENTATION_URLS.general} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-0.5 underline">{t("learnMore")} <ExternalLink className="h-3 w-3" /></a>
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
                {/* Agent Name */}
                <div className="space-y-2">
                    <Label htmlFor="workflow_name" className="text-sm font-medium">{t("agentNameLabel")}</Label>
                    <Input
                        id="workflow_name"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder={t("agentNamePlaceholder")}
                    />
                </div>

                <Separator />

                {/* Ambient Noise */}
                <div className="space-y-4">
                    <div>
                        <h3 className="text-sm font-medium">{t("ambientNoiseTitle")}</h3>
                        <p className="text-xs text-muted-foreground mt-0.5">
                            {t("ambientNoiseDescription")}
                        </p>
                    </div>
                    <div className="flex items-center justify-between">
                        <Label htmlFor="ambient-noise-enabled" className="text-sm">{t("ambientUseLabel")}</Label>
                        <Switch
                            id="ambient-noise-enabled"
                            checked={ambientNoiseConfig.enabled}
                            onCheckedChange={(checked) =>
                                setAmbientNoiseConfig((prev) => ({ ...prev, enabled: checked }))
                            }
                        />
                    </div>
                    {ambientNoiseConfig.enabled && (
                        <div className="space-y-4">
                            <div className="space-y-2">
                                <Label htmlFor="ambient-volume" className="text-xs">{t("ambientVolumeLabel")}</Label>
                                <Input
                                    id="ambient-volume"
                                    type="number"
                                    step="0.1"
                                    min="0"
                                    max="1"
                                    value={ambientNoiseConfig.volume}
                                    onChange={(e) => {
                                        const value = parseFloat(e.target.value);
                                        if (!isNaN(value)) setAmbientNoiseConfig((prev) => ({ ...prev, volume: value }));
                                    }}
                                />
                            </div>

                            {/* Custom Audio File */}
                            <div className="space-y-2">
                                <Label className="text-xs">{t("customAudioFileLabel")}</Label>
                                <p className="text-xs text-muted-foreground">
                                    {t("customAudioFileDescription")}
                                </p>

                                {ambientNoiseConfig.storage_key ? (
                                    <div className="flex items-center gap-2 rounded-md border p-2 bg-muted/10">
                                        <code className="text-xs bg-muted px-1.5 py-0.5 rounded font-mono truncate flex-1">
                                            {ambientNoiseConfig.original_filename || t("customAudioFallback")}
                                        </code>
                                        <Button
                                            type="button"
                                            size="sm"
                                            variant="ghost"
                                            className="h-6 w-6 p-0 shrink-0"
                                            onClick={async () => {
                                                try {
                                                    await togglePlayback(
                                                        "ambient-noise",
                                                        ambientNoiseConfig.storage_key!,
                                                        ambientNoiseConfig.storage_backend,
                                                    );
                                                } catch {
                                                    setAudioUploadError(t("ambientPlayError"));
                                                }
                                            }}
                                        >
                                            {playingId === "ambient-noise" ? (
                                                <Pause className="w-3.5 h-3.5" />
                                            ) : (
                                                <Play className="w-3.5 h-3.5" />
                                            )}
                                        </Button>
                                        <Button
                                            type="button"
                                            size="sm"
                                            variant="ghost"
                                            className="h-6 w-6 p-0 shrink-0"
                                            onClick={handleRemoveCustomAudio}
                                        >
                                            <X className="w-3.5 h-3.5" />
                                        </Button>
                                    </div>
                                ) : (
                                    <div>
                                        <input
                                            ref={ambientFileInputRef}
                                            type="file"
                                            accept="audio/*"
                                            onChange={(e) => {
                                                const file = e.target.files?.[0];
                                                if (file) handleAmbientFileUpload(file);
                                            }}
                                            className="hidden"
                                        />
                                        <Button
                                            type="button"
                                            variant="outline"
                                            size="sm"
                                            className="text-sm font-normal"
                                            onClick={() => ambientFileInputRef.current?.click()}
                                            disabled={isUploadingAudio}
                                        >
                                            {isUploadingAudio ? (
                                                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                                            ) : (
                                                <Upload className="w-4 h-4 mr-2" />
                                            )}
                                            {isUploadingAudio ? t("uploadingEllipsis") : t("uploadAudioButton")}
                                        </Button>
                                    </div>
                                )}

                                {audioUploadError && (
                                    <p className="text-xs text-destructive">{audioUploadError}</p>
                                )}

                                {!ambientNoiseConfig.storage_key && (
                                    <p className="text-xs text-muted-foreground italic">
                                        {t("usingDefaultOfficeAmbience")}
                                    </p>
                                )}
                            </div>
                        </div>
                    )}
                </div>

                <Separator />

                {/* Turn Detection */}
                <div className="space-y-4">
                    <div>
                        <h3 className="text-sm font-medium">{t("turnDetectionTitle")}</h3>
                        <p className="text-xs text-muted-foreground mt-0.5">
                            {t("turnDetectionDescription")}
                        </p>
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="turn_stop_strategy" className="text-xs">{t("detectionStrategyLabel")}</Label>
                        <Select
                            value={turnStopStrategy}
                            onValueChange={(value: TurnStopStrategy) => setTurnStopStrategy(value)}
                        >
                            <SelectTrigger id="turn_stop_strategy">
                                <SelectValue placeholder={t("selectStrategyPlaceholder")} />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value="transcription">{t("strategyTranscription")}</SelectItem>
                                <SelectItem value="turn_analyzer">{t("strategySmartTurnAnalyzer")}</SelectItem>
                            </SelectContent>
                        </Select>
                        <p className="text-xs text-muted-foreground">
                            {turnStopStrategy === "transcription"
                                ? t("strategyTranscriptionHelp")
                                : t("strategySmartTurnAnalyzerHelp")}
                        </p>
                    </div>
                    {turnStopStrategy === "turn_analyzer" && (
                        <div className="space-y-2">
                            <Label htmlFor="smart_turn_stop_secs" className="text-xs">
                                {t("incompleteTurnTimeoutLabel")}
                            </Label>
                            <Input
                                id="smart_turn_stop_secs"
                                type="number"
                                step="0.5"
                                min="0.5"
                                max="10"
                                value={smartTurnStopSecs}
                                onChange={(e) => {
                                    const value = parseFloat(e.target.value);
                                    if (!isNaN(value) && value >= 0.5) setSmartTurnStopSecs(value);
                                }}
                            />
                            <p className="text-xs text-muted-foreground">
                                {t("incompleteTurnTimeoutHelp")}
                            </p>
                        </div>
                    )}
                </div>

                <Separator />

                {/* Context Compaction */}
                <div className="space-y-4">
                    <div>
                        <h3 className="text-sm font-medium">{t("contextCompactionTitle")}</h3>
                        <p className="text-xs text-muted-foreground mt-0.5">
                            {t("contextCompactionDescription")}
                        </p>
                    </div>
                    <div className="flex items-center justify-between">
                        <Label htmlFor="context-compaction-enabled" className="text-sm">
                            {t("contextCompactionEnableLabel")}
                        </Label>
                        <Switch
                            id="context-compaction-enabled"
                            checked={contextCompactionEnabled}
                            onCheckedChange={setContextCompactionEnabled}
                        />
                    </div>
                </div>

                <Separator />

                {/* Call Management */}
                <div className="space-y-4">
                    <div>
                        <h3 className="text-sm font-medium">{t("callManagementTitle")}</h3>
                        <p className="text-xs text-muted-foreground mt-0.5">
                            {t("callManagementDescription")}
                        </p>
                    </div>
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label htmlFor="max_call_duration" className="text-xs">{t("maxCallDurationLabel")}</Label>
                            <Input
                                id="max_call_duration"
                                type="number"
                                min="1"
                                value={maxCallDuration}
                                onChange={(e) => {
                                    const value = parseInt(e.target.value);
                                    if (!isNaN(value) && value > 0) setMaxCallDuration(value);
                                }}
                            />
                            <p className="text-xs text-muted-foreground">{t("maxCallDurationHelp")}</p>
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="max_user_idle_timeout" className="text-xs">
                                {t("maxUserIdleTimeoutLabel")}
                            </Label>
                            <Input
                                id="max_user_idle_timeout"
                                type="number"
                                min="1"
                                value={maxUserIdleTimeout}
                                onChange={(e) => {
                                    const value = parseInt(e.target.value);
                                    if (!isNaN(value) && value > 0) setMaxUserIdleTimeout(value);
                                }}
                            />
                            <p className="text-xs text-muted-foreground">{t("maxUserIdleTimeoutHelp")}</p>
                        </div>
                    </div>
                </div>
            </CardContent>
            <CardFooter className="justify-end gap-3 border-t pt-6">
                {isDirty && <span className="text-xs text-muted-foreground">{t("unsavedChanges")}</span>}
                <Button onClick={handleSave} disabled={isSaving || !isDirty}>
                    {isSaving ? t("savingEllipsis") : t("saveGeneralSettings")}
                </Button>
            </CardFooter>
        </Card>
    );
}

// ---------------------------------------------------------------------------
// Section: Template Variables
// ---------------------------------------------------------------------------

function TemplateVariablesSection({
    templateContextVariables,
    onSave,
}: {
    templateContextVariables: Record<string, string>;
    onSave: (variables: Record<string, string>) => Promise<void>;
}) {
    const t = useTranslations("pages.workflow.workflowId.settings");
    const [contextVars, setContextVars] = useState<Record<string, string>>(templateContextVariables);
    const [newKey, setNewKey] = useState("");
    const [newValue, setNewValue] = useState("");
    const [isSaving, setIsSaving] = useState(false);

    const isDirty = useMemo(() => {
        const pendingVars = newKey && newValue ? { ...contextVars, [newKey]: newValue } : contextVars;
        return JSON.stringify(pendingVars) !== JSON.stringify(templateContextVariables);
    }, [contextVars, newKey, newValue, templateContextVariables]);

    useUnsavedChanges("variables", isDirty);

    const handleAdd = () => {
        if (newKey && newValue) {
            setContextVars((prev) => ({ ...prev, [newKey]: newValue }));
        }
        setNewKey("");
        setNewValue("");
    };

    const handleRemove = (key: string) => {
        setContextVars((prev) => {
            const next = { ...prev };
            delete next[key];
            return next;
        });
    };

    const handleSave = async () => {
        setIsSaving(true);
        try {
            let varsToSave = contextVars;
            if (newKey && newValue) {
                varsToSave = { ...varsToSave, [newKey]: newValue };
            }
            await onSave(varsToSave);
        } catch (error) {
            console.error("Failed to save variables:", error);
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <Card id="variables">
            <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                    <Variable className="h-4 w-4" />
                    {t("templateVariablesTitle")}
                </CardTitle>
                <CardDescription>
                    {t("templateVariablesDescription", { syntax: "{{variable_name}}" })}{" "}
                    <a href={SETTINGS_DOCUMENTATION_URLS.templateVariables} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-0.5 underline">{t("learnMore")} <ExternalLink className="h-3 w-3" /></a>
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                {/* Existing Variables */}
                {Object.entries(contextVars).length > 0 && (
                    <div className="space-y-2">
                        <Label className="text-sm font-medium">{t("currentVariablesLabel")}</Label>
                        {Object.entries(contextVars).map(([key, value]) => (
                            <div key={key} className="flex items-center gap-2 rounded-md border p-2">
                                <div className="flex-1 min-w-0">
                                    <div className="text-sm font-medium">{key}</div>
                                    <div className="text-xs text-muted-foreground truncate">{value}</div>
                                </div>
                                <Button size="sm" variant="ghost" onClick={() => handleRemove(key)}>
                                    <Trash2Icon className="h-4 w-4" />
                                </Button>
                            </div>
                        ))}
                    </div>
                )}

                {/* Add New Variable */}
                <div className="space-y-3">
                    <Label className="text-sm font-medium">{t("addNewVariableLabel")}</Label>
                    <div className="flex gap-2">
                        <div className="flex-1 space-y-1">
                            <Label htmlFor="var-key" className="text-xs">{t("variableKeyLabel")}</Label>
                            <Input
                                id="var-key"
                                placeholder={t("variableKeyPlaceholder")}
                                value={newKey}
                                onChange={(e) => setNewKey(e.target.value)}
                            />
                        </div>
                        <div className="flex-1 space-y-1">
                            <Label htmlFor="var-value" className="text-xs">{t("variableValueLabel")}</Label>
                            <Input
                                id="var-value"
                                placeholder={t("variableValuePlaceholder")}
                                value={newValue}
                                onChange={(e) => setNewValue(e.target.value)}
                            />
                        </div>
                    </div>
                    <Button size="sm" onClick={handleAdd} disabled={!newKey || !newValue}>
                        {t("addVariableButton")}
                    </Button>
                </div>
            </CardContent>
            <CardFooter className="justify-end gap-3 border-t pt-6">
                {isDirty && <span className="text-xs text-muted-foreground">{t("unsavedChanges")}</span>}
                <Button onClick={handleSave} disabled={isSaving || !isDirty}>
                    {isSaving ? t("savingEllipsis") : t("saveVariables")}
                </Button>
            </CardFooter>
        </Card>
    );
}

// ---------------------------------------------------------------------------
// Section: Dictionary
// ---------------------------------------------------------------------------

function DictionarySection({
    dictionary,
    onSave,
}: {
    dictionary: string;
    onSave: (dictionary: string) => Promise<void>;
}) {
    const t = useTranslations("pages.workflow.workflowId.settings");
    const [dictionaryValue, setDictionaryValue] = useState(dictionary);
    const [isSaving, setIsSaving] = useState(false);

    const isDirty = dictionaryValue !== dictionary;

    useUnsavedChanges("dictionary", isDirty);

    const handleSave = async () => {
        setIsSaving(true);
        try {
            await onSave(dictionaryValue);
        } catch (error) {
            console.error("Failed to save dictionary:", error);
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <Card id="dictionary">
            <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                    <BookA className="h-4 w-4" />
                    {t("dictionaryTitle")}
                </CardTitle>
                <CardDescription>
                    {t("dictionaryDescription")}
                </CardDescription>
            </CardHeader>
            <CardContent>
                <Textarea
                    placeholder={t("dictionaryPlaceholder")}
                    value={dictionaryValue}
                    onChange={(e) => setDictionaryValue(e.target.value)}
                    rows={4}
                    className="resize-none"
                />
            </CardContent>
            <CardFooter className="justify-end gap-3 border-t pt-6">
                {isDirty && <span className="text-xs text-muted-foreground">{t("unsavedChanges")}</span>}
                <Button onClick={handleSave} disabled={isSaving || !isDirty}>
                    {isSaving ? t("savingEllipsis") : t("saveDictionary")}
                </Button>
            </CardFooter>
        </Card>
    );
}

// ---------------------------------------------------------------------------
// Section: Voicemail Detection
// ---------------------------------------------------------------------------

function VoicemailSection({
    workflowConfigurations,
    workflowName,
    onSave,
}: {
    workflowConfigurations: WorkflowConfigurations;
    workflowName: string;
    onSave: (configurations: WorkflowConfigurations, workflowName: string) => Promise<void>;
}) {
    const t = useTranslations("pages.workflow.workflowId.settings");
    const getConfig = (): VoicemailDetectionConfiguration => ({
        ...DEFAULT_VOICEMAIL_DETECTION_CONFIGURATION,
        ...workflowConfigurations.voicemail_detection,
    });

    const [enabled, setEnabled] = useState(getConfig().enabled);
    const [useWorkflowLlm, setUseWorkflowLlm] = useState(getConfig().use_workflow_llm);
    const [provider, setProvider] = useState(getConfig().provider || "openai");
    const [model, setModel] = useState(getConfig().model || "gpt-4.1");
    const [apiKey, setApiKey] = useState(getConfig().api_key || "");
    const [systemPrompt, setSystemPrompt] = useState(getConfig().system_prompt || DEFAULT_VOICEMAIL_SYSTEM_PROMPT);
    const [longSpeechTimeout, setLongSpeechTimeout] = useState(getConfig().long_speech_timeout);
    const [isSaving, setIsSaving] = useState(false);

    const isDirty = useMemo(() => {
        const init = {
            ...DEFAULT_VOICEMAIL_DETECTION_CONFIGURATION,
            ...workflowConfigurations.voicemail_detection,
        };
        return (
            enabled !== init.enabled ||
            useWorkflowLlm !== init.use_workflow_llm ||
            provider !== (init.provider || "openai") ||
            model !== (init.model || "gpt-4.1") ||
            apiKey !== (init.api_key || "") ||
            systemPrompt !== (init.system_prompt || DEFAULT_VOICEMAIL_SYSTEM_PROMPT) ||
            longSpeechTimeout !== init.long_speech_timeout
        );
    }, [enabled, useWorkflowLlm, provider, model, apiKey, systemPrompt, longSpeechTimeout, workflowConfigurations]);

    useUnsavedChanges("voicemail", isDirty);

    const handleSave = async () => {
        setIsSaving(true);
        try {
            const voicemailConfig: VoicemailDetectionConfiguration = {
                enabled,
                use_workflow_llm: useWorkflowLlm,
                provider: useWorkflowLlm ? undefined : provider,
                model: useWorkflowLlm ? undefined : model,
                api_key: useWorkflowLlm ? undefined : apiKey,
                system_prompt:
                    systemPrompt && systemPrompt !== DEFAULT_VOICEMAIL_SYSTEM_PROMPT ? systemPrompt : undefined,
                long_speech_timeout: longSpeechTimeout,
            };
            await onSave(
                { ...workflowConfigurations, voicemail_detection: voicemailConfig },
                workflowName,
            );
        } catch (error) {
            console.error("Failed to save voicemail settings:", error);
        } finally {
            setIsSaving(false);
        }
    };

    return (
        <Card id="voicemail">
            <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                    <PhoneOff className="h-4 w-4" />
                    {t("voicemailTitle")}
                </CardTitle>
                <CardDescription>
                    {t("voicemailDescription")}
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                <div className="flex items-center space-x-2 rounded-md border bg-muted/20 p-2">
                    <Switch id="voicemail-enabled" checked={enabled} onCheckedChange={setEnabled} />
                    <Label htmlFor="voicemail-enabled">{t("voicemailEnableLabel")}</Label>
                </div>

                {enabled && (
                    <>
                        {/* LLM Configuration */}
                        <div className="space-y-3">
                            <div className="flex items-center space-x-2 rounded-md border bg-muted/20 p-2">
                                <Switch
                                    id="voicemail-use-workflow-llm"
                                    checked={useWorkflowLlm}
                                    onCheckedChange={setUseWorkflowLlm}
                                />
                                <Label htmlFor="voicemail-use-workflow-llm">{t("useWorkflowLlmLabel")}</Label>
                                <Label className="ml-2 text-xs text-muted-foreground">
                                    {t("useWorkflowLlmHelp")}
                                </Label>
                            </div>

                            {!useWorkflowLlm && (
                                <LLMConfigSelector
                                    provider={provider}
                                    onProviderChange={setProvider}
                                    model={model}
                                    onModelChange={setModel}
                                    apiKey={apiKey}
                                    onApiKeyChange={setApiKey}
                                />
                            )}
                        </div>

                        {/* System Prompt */}
                        <div className="space-y-2">
                            <Label>{t("systemPromptLabel")}</Label>
                            <p className="text-xs text-muted-foreground">
                                {t("systemPromptHelp")}
                            </p>
                            <Textarea
                                value={systemPrompt}
                                onChange={(e) => setSystemPrompt(e.target.value)}
                                className="min-h-[200px] font-mono text-xs"
                            />
                        </div>

                        {/* Timing */}
                        <div className="space-y-2 rounded-md border bg-muted/10 p-3">
                            <Label className="font-medium">{t("timingLabel")}</Label>
                            <div className="space-y-2">
                                <Label className="text-sm">{t("speechCutoffLabel")}</Label>
                                <p className="text-xs text-muted-foreground">
                                    {t("speechCutoffHelp")}
                                </p>
                                <Input
                                    type="number"
                                    step="0.5"
                                    min="1"
                                    max="30"
                                    value={longSpeechTimeout}
                                    onChange={(e) => setLongSpeechTimeout(parseFloat(e.target.value) || 8.0)}
                                />
                            </div>
                        </div>
                    </>
                )}
            </CardContent>
            <CardFooter className="justify-end gap-3 border-t pt-6">
                {isDirty && <span className="text-xs text-muted-foreground">{t("unsavedChanges")}</span>}
                <Button onClick={handleSave} disabled={isSaving || !isDirty}>
                    {isSaving ? t("savingEllipsis") : t("saveVoicemailSettings")}
                </Button>
            </CardFooter>
        </Card>
    );
}

// ---------------------------------------------------------------------------
// Section: Agent UUID
// ---------------------------------------------------------------------------

function AgentUuidSection({ workflowUuid }: { workflowUuid: string }) {
    const t = useTranslations("pages.workflow.workflowId.settings");
    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(workflowUuid);
            toast.success(t("agentUuidCopied"));
        } catch {
            toast.error(t("agentUuidCopyError"));
        }
    };

    return (
        <Card id="identity">
            <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                    <Fingerprint className="h-4 w-4" />
                    {t("agentUuidTitle")}
                </CardTitle>
                <CardDescription>
                    {t("agentUuidDescription")}
                </CardDescription>
            </CardHeader>
            <CardContent>
                <button
                    type="button"
                    onClick={handleCopy}
                    title={t("clickToCopy")}
                    className="group flex w-full items-center gap-2 rounded-md border bg-muted/20 p-2 text-left font-mono text-xs transition-colors hover:bg-muted/40"
                >
                    <code className="flex-1 truncate">{workflowUuid}</code>
                    <Clipboard className="h-3.5 w-3.5 shrink-0 text-muted-foreground transition-colors group-hover:text-foreground" />
                </button>
            </CardContent>
            <CardFooter className="border-t pt-6">
                <Button variant="outline" size="sm" onClick={handleCopy}>
                    <Clipboard className="h-3.5 w-3.5 mr-2" />
                    {t("copyUuidButton")}
                </Button>
            </CardFooter>
        </Card>
    );
}

// ---------------------------------------------------------------------------
// Section: Model Overrides
// ---------------------------------------------------------------------------

function withoutModelConfigurationOverrides(configurations: WorkflowConfigurations): WorkflowConfigurations {
    const next = { ...configurations };
    delete next.model_overrides;
    delete next.model_configuration_v2_override;
    return next;
}

function WorkflowModelOverridesSection({
    workflowConfigurations,
    workflowName,
    onSave,
    modelConfigurationDefaults,
    organizationModelConfiguration,
    modelConfigurationLoading,
    modelConfigurationError,
}: {
    workflowConfigurations: WorkflowConfigurations;
    workflowName: string;
    onSave: (configurations: WorkflowConfigurations, workflowName: string) => Promise<void>;
    modelConfigurationDefaults: ModelConfigurationDefaultsV2 | null;
    organizationModelConfiguration: OrganizationAiModelConfigurationResponse | null;
    modelConfigurationLoading: boolean;
    modelConfigurationError: string | null;
}) {
    const t = useTranslations("pages.workflow.workflowId.settings");
    const savedV2Override = workflowConfigurations.model_configuration_v2_override;
    const hasSavedModelOverride = Boolean(savedV2Override || workflowConfigurations.model_overrides);
    const [overrideEnabled, setOverrideEnabled] = useState(Boolean(savedV2Override));
    const [isRemovingOverride, setIsRemovingOverride] = useState(false);

    useEffect(() => {
        setOverrideEnabled(Boolean(workflowConfigurations.model_configuration_v2_override));
    }, [workflowConfigurations.model_configuration_v2_override]);

    const source = organizationModelConfiguration?.source || "empty";
    const isV2 = source === "organization_v2";

    const saveLegacyOverrides = async (config: Record<string, unknown>) => {
        const nextConfigurations = withoutModelConfigurationOverrides(workflowConfigurations);
        const modelOverrides = config.model_overrides as WorkflowConfigurations["model_overrides"] | undefined;
        if (modelOverrides) {
            nextConfigurations.model_overrides = modelOverrides;
        }
        await onSave(nextConfigurations, workflowName);
    };

    const saveV2Override = async (configuration: OrganizationAiModelConfigurationV2) => {
        const nextConfigurations = withoutModelConfigurationOverrides(workflowConfigurations);
        nextConfigurations.model_configuration_v2_override = configuration;
        await onSave(nextConfigurations, workflowName);
        toast.success(t("modelOverrideSavedToast"));
    };

    const removeV2Override = async () => {
        setIsRemovingOverride(true);
        try {
            await onSave(withoutModelConfigurationOverrides(workflowConfigurations), workflowName);
            setOverrideEnabled(false);
            toast.success(t("usingOrgConfigurationToast"));
        } finally {
            setIsRemovingOverride(false);
        }
    };

    return (
        <Card id="models">
            <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                    <Brain className="h-4 w-4" />
                    {t("modelOverridesTitle")}
                </CardTitle>
                <CardDescription>
                    {isV2
                        ? t("modelOverridesDescriptionV2")
                        : t("modelOverridesDescription")}{" "}
                    <a href={SETTINGS_DOCUMENTATION_URLS.modelOverrides} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-0.5 underline">{t("learnMore")} <ExternalLink className="h-3 w-3" /></a>
                </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
                {modelConfigurationLoading && (
                    <div className="flex items-center gap-2 rounded-md border p-4 text-sm text-muted-foreground">
                        <Loader2 className="h-4 w-4 animate-spin" />
                        {t("modelConfigLoading")}
                    </div>
                )}

                {modelConfigurationError && (
                    <div className="rounded-md border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                        {modelConfigurationError}
                    </div>
                )}

                {!modelConfigurationLoading && !modelConfigurationError && !isV2 && (
                    <>
                        {source === "legacy_user_v1" && (
                            <div className="flex flex-col gap-3 rounded-md border bg-muted/30 p-4 sm:flex-row sm:items-center sm:justify-between">
                                <p className="text-sm text-muted-foreground">
                                    {t("legacyOverrideNotice")}
                                </p>
                                <Button type="button" variant="outline" size="sm" asChild>
                                    <Link href="/model-configurations?action=migrate_to_v2">{t("migrateToV2")}</Link>
                                </Button>
                            </div>
                        )}
                        <ServiceConfigurationForm
                            mode="override"
                            currentOverrides={workflowConfigurations.model_overrides}
                            submitLabel={t("saveModelOverrides")}
                            onSave={saveLegacyOverrides}
                        />
                    </>
                )}

                {!modelConfigurationLoading && !modelConfigurationError && isV2 && modelConfigurationDefaults && organizationModelConfiguration && (
                    <>
                        <div className="flex items-center justify-between rounded-md border p-4">
                            <div className="space-y-0.5">
                                <Label htmlFor="workflow-model-v2-override" className="text-sm font-medium">
                                    {t("overrideForThisWorkflow")}
                                </Label>
                                <p className="text-xs text-muted-foreground">
                                    {overrideEnabled
                                        ? t("overrideEnabledHelp")
                                        : t("overrideDisabledHelp")}
                                </p>
                            </div>
                            <Switch
                                id="workflow-model-v2-override"
                                checked={overrideEnabled}
                                onCheckedChange={setOverrideEnabled}
                            />
                        </div>

                        {overrideEnabled ? (
                            <AIModelConfigurationV2Editor
                                defaults={modelConfigurationDefaults}
                                configuration={
                                    (savedV2Override as OrganizationAiModelConfigurationV2 | undefined)
                                    || (organizationModelConfiguration.configuration as OrganizationAiModelConfigurationV2 | null)
                                }
                                effectiveConfiguration={
                                    savedV2Override
                                        ? null
                                        : organizationModelConfiguration.effective_configuration
                                }
                                submitLabel={t("saveModelOverride")}
                                onSave={saveV2Override}
                            />
                        ) : (
                            <div className="rounded-md border bg-muted/20 p-4">
                                <p className="text-sm text-muted-foreground">
                                    {t("usingOrgConfiguration")}
                                </p>
                                {hasSavedModelOverride && (
                                    <Button
                                        type="button"
                                        variant="outline"
                                        className="mt-3"
                                        onClick={removeV2Override}
                                        disabled={isRemovingOverride}
                                    >
                                        {isRemovingOverride ? t("savingEllipsis") : t("saveOrgConfiguration")}
                                    </Button>
                                )}
                            </div>
                        )}
                    </>
                )}
            </CardContent>
        </Card>
    );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Page wrapper — handles auth & data fetching, then mounts the content
// component only when everything is loaded. This avoids useWorkflowState
// running with empty initial values and overwriting the Zustand store.
// ---------------------------------------------------------------------------

export default function WorkflowSettingsPage() {
    const t = useTranslations("pages.workflow.workflowId.settings");
    const params = useParams();
    const { user, redirectToLogin, loading: authLoading } = useAuth();
    const [workflow, setWorkflow] = useState<WorkflowResponse | undefined>(undefined);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!authLoading && !user) {
            redirectToLogin();
        }
    }, [authLoading, user, redirectToLogin]);

    useEffect(() => {
        const fetchWorkflow = async () => {
            if (!user) return;
            try {
                const response = await getWorkflowApiV1WorkflowFetchWorkflowIdGet({
                    path: { workflow_id: Number(params.workflowId) },
                });
                setWorkflow(response.data);
            } catch (err) {
                setError(t("fetchWorkflowError"));
                logger.error(`Error fetching workflow settings: ${err}`);
            } finally {
                setLoading(false);
            }
        };
        if (user) fetchWorkflow();
    }, [params.workflowId, user, t]);

    if (loading || authLoading) return <SpinLoader />;

    if (error || !workflow) {
        return (
            <div className="flex min-h-screen items-center justify-center">
                <div className="text-lg text-destructive">{error || t("workflowNotFound")}</div>
            </div>
        );
    }

    if (!user) return null;

    return <WorkflowSettingsContent workflow={workflow} user={user} />;
}

// ---------------------------------------------------------------------------
// Content — only mounts once the workflow API response is available, so
// useWorkflowState always initialises with real data.
// ---------------------------------------------------------------------------

function WorkflowSettingsContent({
    workflow,
    user,
}: {
    workflow: WorkflowResponse;
    user: { id: string; email?: string };
}) {
    return (
        <UnsavedChangesProvider>
            <WorkflowSettingsInner workflow={workflow} user={user} />
        </UnsavedChangesProvider>
    );
}

function WorkflowSettingsInner({
    workflow,
    user,
}: {
    workflow: WorkflowResponse;
    user: { id: string; email?: string };
}) {
    const t = useTranslations("pages.workflow.workflowId.settings");
    const router = useRouter();
    const { dirtySections, confirmNavigate } = useUnsavedChangesContext();

    const [isEmbedDialogOpen, setIsEmbedDialogOpen] = useState(false);
    const [activeSection, setActiveSection] = useState("general");
    const [modelConfigurationDefaults, setModelConfigurationDefaults] = useState<ModelConfigurationDefaultsV2 | null>(null);
    const [organizationModelConfiguration, setOrganizationModelConfiguration] = useState<OrganizationAiModelConfigurationResponse | null>(null);
    const [modelConfigurationLoading, setModelConfigurationLoading] = useState(true);
    const [modelConfigurationError, setModelConfigurationError] = useState<string | null>(null);
    const hasFetchedModelConfiguration = useRef(false);

    const workflowId = workflow.id;

    const initialFlow = useMemo(
        () => ({
            nodes: workflow.workflow_definition.nodes as FlowNode[],
            edges: workflow.workflow_definition.edges as FlowEdge[],
            viewport: { x: 0, y: 0, zoom: 0 },
        }),
        [workflow],
    );

    const initialTemplateContextVariables = useMemo(
        () => (workflow.template_context_variables as Record<string, string>) || {},
        [workflow],
    );

    const initialWorkflowConfigurations = useMemo(
        () => (workflow.workflow_configurations as WorkflowConfigurations) || DEFAULT_WORKFLOW_CONFIGURATIONS,
        [workflow],
    );

    const {
        workflowName,
        workflowConfigurations,
        templateContextVariables,
        dictionary,
        saveWorkflowConfigurations,
        saveTemplateContextVariables,
        saveDictionary,
    } = useWorkflowState({
        initialWorkflowName: workflow.name,
        workflowId,
        initialFlow,
        initialTemplateContextVariables,
        initialWorkflowConfigurations,
        user,
    });

    useEffect(() => {
        if (hasFetchedModelConfiguration.current) return;
        hasFetchedModelConfiguration.current = true;

        const loadModelConfiguration = async () => {
            setModelConfigurationLoading(true);
            setModelConfigurationError(null);
            const [defaultsResult, configurationResult] = await Promise.all([
                getModelConfigurationV2DefaultsApiV1OrganizationsModelConfigurationsV2DefaultsGet(),
                getModelConfigurationV2ApiV1OrganizationsModelConfigurationsV2Get(),
            ]);

            if (defaultsResult.error) {
                setModelConfigurationError(detailFromError(defaultsResult.error, "Failed to load model configuration defaults"));
                setModelConfigurationLoading(false);
                return;
            }
            if (configurationResult.error) {
                setModelConfigurationError(detailFromError(configurationResult.error, "Failed to load model configuration"));
                setModelConfigurationLoading(false);
                return;
            }

            setModelConfigurationDefaults(defaultsResult.data as ModelConfigurationDefaultsV2);
            setOrganizationModelConfiguration(configurationResult.data || null);
            setModelConfigurationLoading(false);
        };

        loadModelConfiguration();
    }, []);

    // Intersection observer for active sidebar link
    useEffect(() => {
        const ids = NAV_ITEMS.map((n) => n.id);
        const observer = new IntersectionObserver(
            (entries) => {
                for (const entry of entries) {
                    if (entry.isIntersecting) {
                        setActiveSection(entry.target.id);
                        break;
                    }
                }
            },
            { rootMargin: "-20% 0px -60% 0px" },
        );
        ids.forEach((id) => {
            const el = document.getElementById(id);
            if (el) observer.observe(el);
        });
        return () => observer.disconnect();
    }, []);

    return (
        <div className="min-h-screen">
            {/* Sticky header */}
            <header className="sticky top-0 z-10 flex items-center gap-3 border-b bg-background/95 px-6 py-3 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => confirmNavigate(() => router.push(`/workflow/${workflowId}`))}
                >
                    <ArrowLeft className="h-4 w-4" />
                </Button>
                <div>
                    <p className="text-xs text-muted-foreground">{t("workflowSettingsHeader")}</p>
                    <h1 className="text-sm font-semibold">{workflowName || workflow.name}</h1>
                </div>
            </header>

            {/* Main + right nav */}
            <div className="mx-auto flex max-w-5xl gap-8 px-6 py-8">
                {/* Sections */}
                <div className="min-w-0 flex-1 space-y-8">
                    {workflowConfigurations && (
                        <>
                            {/* General */}
                            <GeneralSection
                                workflowConfigurations={workflowConfigurations}
                                workflowName={workflowName || workflow.name}
                                workflowId={workflowId}
                                onSave={saveWorkflowConfigurations}
                            />

                            {/* Model Overrides */}
                            <WorkflowModelOverridesSection
                                workflowConfigurations={workflowConfigurations}
                                workflowName={workflowName}
                                onSave={saveWorkflowConfigurations}
                                modelConfigurationDefaults={modelConfigurationDefaults}
                                organizationModelConfiguration={organizationModelConfiguration}
                                modelConfigurationLoading={modelConfigurationLoading}
                                modelConfigurationError={modelConfigurationError}
                            />

                            {/* Template Variables */}
                            <TemplateVariablesSection
                                templateContextVariables={templateContextVariables}
                                onSave={saveTemplateContextVariables}
                            />

                            {/* Dictionary */}
                            <DictionarySection dictionary={dictionary} onSave={saveDictionary} />

                            {/* Voicemail Detection */}
                            <VoicemailSection
                                workflowConfigurations={workflowConfigurations}
                                workflowName={workflowName}
                                onSave={saveWorkflowConfigurations}
                            />

                            {/* Recordings – moved to org-level page */}
                            <Card id="recordings">
                                <CardHeader>
                                    <CardTitle className="flex items-center gap-2 text-base">
                                        <Mic className="h-4 w-4" />
                                        {t("recordingsTitle")}
                                    </CardTitle>
                                    <CardDescription>
                                        {t.rich("recordingsDescription", {
                                            code: (chunks) => <code className="rounded bg-muted px-1 text-xs">{chunks}</code>,
                                        })}{" "}
                                        <a href={SETTINGS_DOCUMENTATION_URLS.recordings} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-0.5 underline">{t("learnMore")} <ExternalLink className="h-3 w-3" /></a>
                                    </CardDescription>
                                </CardHeader>
                                <CardFooter className="border-t pt-6">
                                    <Button variant="outline" asChild>
                                        <Link href="/recordings">
                                            {t("goToRecordings")}
                                            <ExternalLink className="ml-2 h-4 w-4" />
                                        </Link>
                                    </Button>
                                </CardFooter>
                            </Card>

                            {/* Deployment (dialog trigger) */}
                            <Card id="deployment">
                                <CardHeader>
                                    <CardTitle className="flex items-center gap-2 text-base">
                                        <Rocket className="h-4 w-4" />
                                        {t("deploymentTitle")}
                                    </CardTitle>
                                    <CardDescription>
                                        {t("deploymentDescription")}{" "}
                                        <a href={SETTINGS_DOCUMENTATION_URLS.deployment} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-0.5 underline">{t("learnMore")} <ExternalLink className="h-3 w-3" /></a>
                                    </CardDescription>
                                </CardHeader>
                                <CardFooter className="border-t pt-6">
                                    <Button variant="outline" onClick={() => setIsEmbedDialogOpen(true)}>
                                        {t("configureWidget")}
                                    </Button>
                                </CardFooter>
                            </Card>

                            {/* Report */}
                            <ReportSection workflowId={workflowId} />

                            {/* Agent UUID */}
                            {workflow.workflow_uuid && (
                                <AgentUuidSection workflowUuid={workflow.workflow_uuid} />
                            )}
                        </>
                    )}
                </div>

                {/* ---- Right-side sticky nav ---- */}
                <nav className="hidden w-44 shrink-0 lg:block">
                    <div className="sticky top-20 space-y-1">
                        <p className="mb-2 text-xs font-medium uppercase tracking-wider text-muted-foreground">
                            {t("onThisPage")}
                        </p>
                        {NAV_ITEMS.map((item) => (
                            <a
                                key={item.id}
                                href={`#${item.id}`}
                                className={`flex items-center gap-1.5 rounded-md px-2 py-1 text-sm transition-colors hover:text-foreground ${
                                    activeSection === item.id
                                        ? "font-medium text-foreground"
                                        : "text-muted-foreground"
                                }`}
                            >
                                {t(item.labelKey)}
                                {dirtySections.has(item.id) && (
                                    <span className="h-1.5 w-1.5 rounded-full bg-orange-500" />
                                )}
                            </a>
                        ))}
                    </div>
                </nav>
            </div>

            {/* Dialogs for complex sections */}
            <EmbedDialog
                open={isEmbedDialogOpen}
                onOpenChange={setIsEmbedDialogOpen}
                workflowId={workflowId}
                workflowName={workflowName || workflow.name}
            />
        </div>
    );
}
