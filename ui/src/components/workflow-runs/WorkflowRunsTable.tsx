"use client";

import { ArrowDown, ArrowUp, ArrowUpDown, ChevronLeft, ChevronRight, ExternalLink, RefreshCw } from "lucide-react";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { WorkflowRunResponseSchema } from "@/client/types.gen";
import { CallTypeCell } from "@/components/CallTypeCell";
import { FilterBuilder } from "@/components/filters/FilterBuilder";
import { MediaPreviewButton, MediaPreviewDialog } from "@/components/MediaPreviewDialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
    Table,
    TableBody,
    TableCell,
    TableHead,
    TableHeader,
    TableRow,
} from "@/components/ui/table";
import { ActiveFilter, FilterAttribute } from "@/types/filters";

export interface WorkflowRunsTableProps {
    // Data
    runs: WorkflowRunResponseSchema[];
    loading: boolean;
    error: string | null;

    // Pagination
    currentPage: number;
    totalPages: number;
    totalCount: number;
    onPageChange: (page: number) => void;

    // Filters
    availableAttributes: FilterAttribute[];
    activeFilters: ActiveFilter[];
    onFiltersChange: (filters: ActiveFilter[]) => void;
    onApplyFilters: () => void;
    onClearFilters: () => void;
    isExecutingFilters: boolean;
    hasAppliedFilters?: boolean;

    // Sorting
    sortBy?: string | null;
    sortOrder?: 'asc' | 'desc';
    onSort?: (field: string) => void;

    // Navigation & Actions
    workflowId: number;

    // Reload
    onReload?: () => void;

    // Optional customization
    title?: string;
    subtitle?: string;
    showFilters?: boolean;
    emptyMessage?: string;
}

export function WorkflowRunsTable({
    runs,
    loading,
    error,
    currentPage,
    totalPages,
    totalCount,
    onPageChange,
    availableAttributes,
    activeFilters,
    onFiltersChange,
    onApplyFilters,
    onClearFilters,
    isExecutingFilters,
    hasAppliedFilters = false,
    sortBy,
    sortOrder = 'desc',
    onSort,
    workflowId,
    onReload,
    title,
    subtitle,
    showFilters = true,
    emptyMessage,
}: WorkflowRunsTableProps) {
    const t = useTranslations("components.workflowRuns.workflowRunsTable");
    const [selectedRowId, setSelectedRowId] = useState<number | null>(null);

    const resolvedTitle = title ?? t("title");
    const resolvedEmptyMessage = emptyMessage ?? t("emptyMessage");

    // Media preview dialog
    const mediaPreview = MediaPreviewDialog();

    const formatDate = (dateString: string) => new Date(dateString).toLocaleString();

    const handleRowClick = (runId: number) => {
        window.open(`/workflow/${workflowId}/run/${runId}`, '_blank');
    };

    return (
        <div className="space-y-6">
            {/* Title and Filters */}
            {showFilters && (
                <div className="mb-6">
                    <h1 className="text-2xl font-bold mb-4">{resolvedTitle}</h1>
                    <FilterBuilder
                        availableAttributes={availableAttributes}
                        activeFilters={activeFilters}
                        onFiltersChange={onFiltersChange}
                        onApplyFilters={onApplyFilters}
                        onClearFilters={onClearFilters}
                        isExecuting={isExecutingFilters}
                        hasAppliedFilters={hasAppliedFilters}
                    />
                </div>
            )}

            {/* Loading State */}
            {loading ? (
                <div className="flex justify-center">
                    <div className="animate-pulse">{t("loading")}</div>
                </div>
            ) : error ? (
                <div className="bg-destructive/10 border border-destructive/30 text-destructive px-4 py-3 rounded">
                    {error}
                </div>
            ) : runs.length === 0 ? (
                <div className="text-center py-8">
                    <p className="text-muted-foreground">{resolvedEmptyMessage}</p>
                </div>
            ) : (
                <Card>
                    <CardHeader>
                        <div className="flex items-center justify-between">
                            <div>
                                <CardTitle>{t("cardTitle")}</CardTitle>
                                <CardDescription>
                                    {subtitle || t("showingRuns", { shown: runs.length, total: totalCount })}
                                </CardDescription>
                            </div>
                            {onReload && (
                                <Button
                                    variant="outline"
                                    size="icon"
                                    onClick={onReload}
                                    disabled={loading}
                                    title={t("reload")}
                                >
                                    <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                                </Button>
                            )}
                        </div>
                    </CardHeader>
                    <CardContent>
                        <div className="bg-card border border-border rounded-lg overflow-hidden shadow-sm">
                            <Table>
                                <TableHeader>
                                    <TableRow className="bg-muted/50">
                                        <TableHead className="font-semibold">{t("columnId")}</TableHead>
                                        <TableHead className="font-semibold">{t("columnStatus")}</TableHead>
                                        <TableHead className="font-semibold">{t("columnCreatedAt")}</TableHead>
                                        <TableHead className="font-semibold">{t("columnCallType")}</TableHead>
                                        <TableHead
                                            className="font-semibold cursor-pointer hover:bg-muted/50 select-none"
                                            onClick={() => onSort?.('duration')}
                                        >
                                            <div className="flex items-center gap-1">
                                                {t("columnDuration")}
                                                {sortBy === 'duration' ? (
                                                    sortOrder === 'asc' ? <ArrowUp className="h-4 w-4" /> : <ArrowDown className="h-4 w-4" />
                                                ) : (
                                                    <ArrowUpDown className="h-4 w-4 text-muted-foreground" />
                                                )}
                                            </div>
                                        </TableHead>
                                        <TableHead className="font-semibold">{t("columnDisposition")}</TableHead>
                                        <TableHead className="font-semibold">{t("columnActions")}</TableHead>
                                    </TableRow>
                                </TableHeader>
                                <TableBody>
                                    {runs.map((run) => (
                                        <TableRow
                                            key={run.id}
                                            className={`cursor-pointer hover:bg-muted/50 ${selectedRowId === run.id ? "bg-primary/20 ring-1 ring-primary/50" : ""}`}
                                            onClick={() => handleRowClick(run.id)}
                                        >
                                            <TableCell className="font-mono text-sm">#{run.id}</TableCell>
                                            <TableCell>
                                                <Badge variant={run.is_completed ? "default" : "secondary"}>
                                                    {run.is_completed ? t("statusCompleted") : t("statusInProgress")}
                                                </Badge>
                                            </TableCell>
                                            <TableCell className="text-sm">{formatDate(run.created_at)}</TableCell>
                                            <TableCell>
                                                <CallTypeCell mode={run.mode} callType={run.call_type} />
                                            </TableCell>
                                            <TableCell className="text-sm">
                                                {typeof run.cost_info?.call_duration_seconds === 'number'
                                                    ? `${run.cost_info.call_duration_seconds.toFixed(1)}s`
                                                    : "-"}
                                            </TableCell>
                                            <TableCell>
                                                {run.gathered_context?.mapped_call_disposition ? (
                                                    <Badge variant="default">
                                                        {run.gathered_context.mapped_call_disposition as string}
                                                    </Badge>
                                                ) : (
                                                    <span className="text-sm text-muted-foreground">-</span>
                                                )}
                                            </TableCell>
                                            <TableCell>
                                                <div className="flex space-x-2" onClick={(e) => e.stopPropagation()}>
                                                    <MediaPreviewButton
                                                        recordingUrl={run.recording_url}
                                                        transcriptUrl={run.transcript_url}
                                                        runId={run.id}
                                                        onOpenPreview={mediaPreview.openPreview}
                                                        onSelect={setSelectedRowId}
                                                    />
                                                    <Button
                                                        variant="outline"
                                                        size="icon"
                                                        onClick={() => window.open(`/workflow/${workflowId}/run/${run.id}`, '_blank')}
                                                    >
                                                        <ExternalLink className="h-4 w-4" />
                                                    </Button>
                                                </div>
                                            </TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </div>

                        {/* Pagination */}
                        {totalPages > 1 && (
                            <div className="flex items-center justify-between mt-6">
                                <p className="text-sm text-muted-foreground">
                                    {t("pageOf", { current: currentPage, total: totalPages })}
                                </p>
                                <div className="flex gap-2">
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => onPageChange(currentPage - 1)}
                                        disabled={currentPage === 1}
                                    >
                                        <ChevronLeft className="h-4 w-4" />
                                        {t("previous")}
                                    </Button>
                                    <Button
                                        variant="outline"
                                        size="sm"
                                        onClick={() => onPageChange(currentPage + 1)}
                                        disabled={currentPage === totalPages}
                                    >
                                        {t("next")}
                                        <ChevronRight className="h-4 w-4" />
                                    </Button>
                                </div>
                            </div>
                        )}
                    </CardContent>
                </Card>
            )}

            {/* Media Preview Dialog */}
            {mediaPreview.dialog}
        </div>
    );
}
