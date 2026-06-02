"use client";

import { ExternalLink } from "lucide-react";
import { useTranslations } from "next-intl";

import { ServiceConfigurationForm } from "@/components/ServiceConfigurationForm";
import { useUserConfig } from "@/context/UserConfigContext";

interface ServiceConfigurationProps {
    docsUrl?: string;
}

export default function ServiceConfiguration({ docsUrl }: ServiceConfigurationProps) {
    const { saveUserConfig } = useUserConfig();
    const t = useTranslations("components.serviceConfiguration");

    return (
        <div className="w-full max-w-2xl mx-auto">
            <div className="mb-6">
                <h1 className="text-3xl font-bold mb-2">{t("title")}</h1>
                <p className="text-muted-foreground">
                    {t("description")}{" "}
                    {docsUrl && (
                        <a href={docsUrl} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-0.5 underline">
                            {t("learnMore")} <ExternalLink className="h-3 w-3" />
                        </a>
                    )}
                </p>
            </div>

            <ServiceConfigurationForm
                mode="global"
                onSave={async (config) => {
                    await saveUserConfig(config);
                }}
            />
        </div>
    );
}
