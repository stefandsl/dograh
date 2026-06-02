import { Phone,PhoneForwarded } from 'lucide-react';
import { getTranslations } from 'next-intl/server';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';

interface MetricsCardsProps {
  metrics: {
    total_runs: number;
    xfer_count: number;
  };
}

export async function MetricsCards({ metrics }: MetricsCardsProps) {
  const t = await getTranslations('components.metricsCards');

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">{t('totalWorkflowRuns')}</CardTitle>
          <Phone className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{metrics.total_runs.toLocaleString()}</div>
          <p className="text-xs text-muted-foreground">
            {t('totalCallsProcessedToday')}
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle className="text-sm font-medium">{t('transferDispositions')}</CardTitle>
          <PhoneForwarded className="h-4 w-4 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">{metrics.xfer_count.toLocaleString()}</div>
          <p className="text-xs text-muted-foreground">
            {t('callsTransferredXfer')}
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
