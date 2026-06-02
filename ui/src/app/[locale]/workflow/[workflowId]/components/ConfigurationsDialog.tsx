import { useTranslations } from "next-intl";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { AmbientNoiseConfiguration, TurnStopStrategy, WorkflowConfigurations } from "@/types/workflow-configurations";

interface ConfigurationsDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    workflowConfigurations: WorkflowConfigurations | null;
    workflowName: string;
    onSave: (configurations: WorkflowConfigurations, workflowName: string) => Promise<void>;
}

const DEFAULT_AMBIENT_NOISE_CONFIG: AmbientNoiseConfiguration = {
    enabled: false,
    volume: 0.3,
};

export const ConfigurationsDialog = ({
    open,
    onOpenChange,
    workflowConfigurations,
    workflowName,
    onSave
}: ConfigurationsDialogProps) => {
    const t = useTranslations("components.configurationsDialog");
    const [name, setName] = useState<string>(workflowName);
    const [ambientNoiseConfig, setAmbientNoiseConfig] = useState<AmbientNoiseConfiguration>(
        workflowConfigurations?.ambient_noise_configuration || DEFAULT_AMBIENT_NOISE_CONFIG
    );
    const [maxCallDuration, setMaxCallDuration] = useState<number>(
        workflowConfigurations?.max_call_duration || 600  // Default 10 minutes
    );
    const [maxUserIdleTimeout, setMaxUserIdleTimeout] = useState<number>(
        workflowConfigurations?.max_user_idle_timeout || 10  // Default 10 seconds
    );
    const [smartTurnStopSecs, setSmartTurnStopSecs] = useState<number>(
        workflowConfigurations?.smart_turn_stop_secs || 2  // Default 2 seconds
    );
    const [turnStopStrategy, setTurnStopStrategy] = useState<TurnStopStrategy>(
        workflowConfigurations?.turn_stop_strategy || 'transcription'
    );
    const [contextCompactionEnabled, setContextCompactionEnabled] = useState<boolean>(
        workflowConfigurations?.context_compaction_enabled ?? false
    );
    const [isSaving, setIsSaving] = useState(false);

    const handleSave = async () => {
        setIsSaving(true);
        try {
            await onSave({
                ambient_noise_configuration: ambientNoiseConfig,
                max_call_duration: maxCallDuration,
                max_user_idle_timeout: maxUserIdleTimeout,
                smart_turn_stop_secs: smartTurnStopSecs,
                turn_stop_strategy: turnStopStrategy,
                context_compaction_enabled: contextCompactionEnabled,
            }, name);
            onOpenChange(false);
        } catch (error) {
            console.error("Failed to save configurations:", error);
        } finally {
            setIsSaving(false);
        }
    };

    // Sync state with props when dialog opens
    useEffect(() => {
        if (open) {
            setName(workflowName);
            setAmbientNoiseConfig(workflowConfigurations?.ambient_noise_configuration || DEFAULT_AMBIENT_NOISE_CONFIG);
            setMaxCallDuration(workflowConfigurations?.max_call_duration || 600);
            setMaxUserIdleTimeout(workflowConfigurations?.max_user_idle_timeout || 10);
            setSmartTurnStopSecs(workflowConfigurations?.smart_turn_stop_secs || 2);
            setTurnStopStrategy(workflowConfigurations?.turn_stop_strategy || 'transcription');
            setContextCompactionEnabled(workflowConfigurations?.context_compaction_enabled ?? false);
        }
    }, [open, workflowName, workflowConfigurations]);

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent className="max-w-lg">
                <DialogHeader>
                    <DialogTitle>{t("title")}</DialogTitle>
                </DialogHeader>

                <div className="space-y-6">
                    {/* Workflow Name Section */}
                    <div className="space-y-4">
                        <div>
                            <h3 className="text-sm font-semibold mb-1">{t("agentNameTitle")}</h3>
                            <p className="text-xs text-muted-foreground">
                                {t("agentNameDescription")}
                            </p>
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="workflow_name" className="text-xs">
                                {t("nameLabel")}
                            </Label>
                            <Input
                                id="workflow_name"
                                type="text"
                                value={name}
                                onChange={(e) => setName(e.target.value)}
                                placeholder={t("agentNamePlaceholder")}
                            />
                        </div>
                    </div>

                    {/* Ambient Noise Section */}
                    <div className="space-y-4">
                        <div>
                            <h3 className="text-sm font-semibold mb-1">{t("ambientNoiseTitle")}</h3>
                            <p className="text-xs text-muted-foreground">
                                {t("ambientNoiseDescription")}
                            </p>
                        </div>

                        <div className="space-y-4">
                            <div className="flex items-center justify-between">
                                <Label htmlFor="ambient-noise-enabled" className="text-sm">
                                    {t("useAmbientNoise")}
                                </Label>
                                <Switch
                                    id="ambient-noise-enabled"
                                    checked={ambientNoiseConfig.enabled}
                                    onCheckedChange={(checked) =>
                                        setAmbientNoiseConfig(prev => ({ ...prev, enabled: checked }))
                                    }
                                />
                            </div>

                            {ambientNoiseConfig.enabled && (
                                <div className="space-y-2">
                                    <Label htmlFor="ambient-volume" className="text-xs">
                                        {t("volumeLabel")}
                                    </Label>
                                    <Input
                                        id="ambient-volume"
                                        type="number"
                                        step="0.1"
                                        min="0"
                                        max="1"
                                        value={ambientNoiseConfig.volume}
                                        onChange={(e) => {
                                            const value = parseFloat(e.target.value);
                                            if (!isNaN(value)) {
                                                setAmbientNoiseConfig(prev => ({ ...prev, volume: value }));
                                            }
                                        }}
                                    />
                                </div>
                            )}
                        </div>
                    </div>

                    {/* Turn Detection Section */}
                    <div className="space-y-4">
                        <div>
                            <h3 className="text-sm font-semibold mb-1">{t("turnDetectionTitle")}</h3>
                            <p className="text-xs text-muted-foreground">
                                {t("turnDetectionDescription")}
                            </p>
                        </div>

                        <div className="space-y-2">
                            <Label htmlFor="turn_stop_strategy" className="text-xs">
                                {t("detectionStrategyLabel")}
                            </Label>
                            <Select
                                value={turnStopStrategy}
                                onValueChange={(value: TurnStopStrategy) => setTurnStopStrategy(value)}
                            >
                                <SelectTrigger id="turn_stop_strategy">
                                    <SelectValue placeholder={t("selectStrategyPlaceholder")} />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="transcription">
                                        {t("strategyTranscription")}
                                    </SelectItem>
                                    <SelectItem value="turn_analyzer">
                                        {t("strategySmartTurnAnalyzer")}
                                    </SelectItem>
                                </SelectContent>
                            </Select>
                            <p className="text-xs text-muted-foreground">
                                {turnStopStrategy === 'transcription'
                                    ? t("strategyTranscriptionHelp")
                                    : t("strategySmartTurnAnalyzerHelp")}
                            </p>
                        </div>

                        {turnStopStrategy === 'turn_analyzer' && (
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
                                        if (!isNaN(value) && value >= 0.5) {
                                            setSmartTurnStopSecs(value);
                                        }
                                    }}
                                />
                                <p className="text-xs text-muted-foreground">
                                    {t("incompleteTurnTimeoutHelp")}
                                </p>
                            </div>
                        )}
                    </div>

                    {/* Context Management Section */}
                    <div className="space-y-4">
                        <div>
                            <h3 className="text-sm font-semibold mb-1">{t("contextCompactionTitle")}</h3>
                            <p className="text-xs text-muted-foreground">
                                {t("contextCompactionDescription")}
                            </p>
                        </div>

                        <div className="flex items-center justify-between">
                            <Label htmlFor="context-compaction-enabled" className="text-sm">
                                {t("enableContextCompaction")}
                            </Label>
                            <Switch
                                id="context-compaction-enabled"
                                checked={contextCompactionEnabled}
                                onCheckedChange={setContextCompactionEnabled}
                            />
                        </div>
                    </div>

                    {/* Call Management Section */}
                    <div className="space-y-4">
                        <div>
                            <h3 className="text-sm font-semibold mb-1">{t("callManagementTitle")}</h3>
                            <p className="text-xs text-muted-foreground">
                                {t("callManagementDescription")}
                            </p>
                        </div>

                        <div className="grid grid-cols-2 gap-4">
                            <div className="space-y-2">
                                <Label htmlFor="max_call_duration" className="text-xs">
                                    {t("maxCallDurationLabel")}
                                </Label>
                                <Input
                                    id="max_call_duration"
                                    type="number"
                                    step="1"
                                    min="1"
                                    value={maxCallDuration}
                                    onChange={(e) => {
                                        const value = parseInt(e.target.value);
                                        if (!isNaN(value) && value > 0) {
                                            setMaxCallDuration(value);
                                        }
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
                                    step="1"
                                    min="1"
                                    value={maxUserIdleTimeout}
                                    onChange={(e) => {
                                        const value = parseInt(e.target.value);
                                        if (!isNaN(value) && value > 0) {
                                            setMaxUserIdleTimeout(value);
                                        }
                                    }}
                                />
                                <p className="text-xs text-muted-foreground">{t("maxUserIdleTimeoutHelp")}</p>
                            </div>
                        </div>
                    </div>
                </div>

                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>
                        {t("cancel")}
                    </Button>
                    <Button onClick={handleSave} disabled={isSaving}>
                        {isSaving ? t("saving") : t("save")}
                    </Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
};

