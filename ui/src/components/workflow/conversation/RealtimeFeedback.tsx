"use client";

import { useTranslations } from "next-intl";

import {
    conversationItemsFromLiveFeedback,
    conversationItemsFromRealtimeFeedbackEvents,
} from "./adapters/fromRealtimeFeedback";
import { ConversationContainer } from "./ConversationContainer";
import { ConversationTimeline } from "./ConversationTimeline";
import type {
    ConversationStatus,
    RealtimeFeedbackMessage,
    WorkflowRunLogs,
} from "./types";
import { countConversationMessages } from "./utils";

interface LiveModeProps {
    mode: "live";
    messages: RealtimeFeedbackMessage[];
    isCallActive: boolean;
    isCallCompleted: boolean;
}

interface HistoricalModeProps {
    mode: "historical";
    logs: WorkflowRunLogs | null;
}

type RealtimeFeedbackProps = LiveModeProps | HistoricalModeProps;

export function RealtimeFeedback(props: RealtimeFeedbackProps) {
    const t = useTranslations("components.workflow.conversation.realtimeFeedback");

    let items;
    let status: ConversationStatus;
    let title: string;
    let emptyState: { title: string; subtitle: string };
    let autoScroll = false;

    if (props.mode === "historical") {
        items = props.logs?.realtime_feedback_events
            ? conversationItemsFromRealtimeFeedbackEvents(props.logs.realtime_feedback_events)
            : [];
        status = "ended";
        title = t("callTranscript");
        emptyState = {
            title: t("noConversationRecorded"),
            subtitle: t("noConversationRecordedSubtitle"),
        };
    } else {
        items = conversationItemsFromLiveFeedback(props.messages);
        status = props.isCallActive ? "live" : props.isCallCompleted ? "ended" : "ready";
        title = t("liveTranscript");
        emptyState = {
            title: t("noMessagesYet"),
            subtitle: props.isCallActive
                ? t("startSpeakingSubtitle")
                : t("startCallSubtitle"),
        };
        autoScroll = true;
    }

    return (
        <ConversationContainer
            title={title}
            status={status}
            messageCount={countConversationMessages(items) || undefined}
        >
            <ConversationTimeline
                items={items}
                autoScroll={autoScroll}
                emptyState={emptyState}
            />
        </ConversationContainer>
    );
}
