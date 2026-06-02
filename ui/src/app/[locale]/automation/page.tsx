"use client";

import { Zap } from 'lucide-react';
import { useTranslations } from 'next-intl';

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';

export default function AutomationPage() {
    const t = useTranslations("pages.automation");

    return (
        <div className="container mx-auto p-6 space-y-6">
            <div>
                <h1 className="text-3xl font-bold mb-2">{t("title")}</h1>
                <p>{t("subtitle")}</p>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle>{t("comingSoonTitle")}</CardTitle>
                    <CardDescription>
                        {t("comingSoonDescription")}
                    </CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="text-center py-12">
                        <Zap className="w-16 h-16 mx-auto mb-6" />
                        <p className="text-lg mb-4">
                            {t("intro")}
                        </p>
                        <p>
                            {t("details")}
                        </p>
                        <p className="mt-4">
                            {t("checkBack")}
                        </p>
                    </div>
                </CardContent>
            </Card>
        </div>
    );
}
