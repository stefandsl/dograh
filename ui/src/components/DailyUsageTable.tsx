import { useTranslations } from 'next-intl';

import type { DailyUsageBreakdownResponse } from '@/client/types.gen';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import {
    Table,
    TableBody,
    TableCell,
    TableFooter,
    TableHead,
    TableHeader,
    TableRow,
} from '@/components/ui/table';

interface DailyUsageTableProps {
    data: DailyUsageBreakdownResponse | null;
    isLoading: boolean;
}

export function DailyUsageTable({ data, isLoading }: DailyUsageTableProps) {
    const t = useTranslations('components.dailyUsageTable');

    // Format date for display
    const formatDate = (dateString: string) => {
        const date = new Date(dateString);
        return date.toLocaleDateString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric'
        });
    };

    if (isLoading) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle>{t('title')}</CardTitle>
                    <CardDescription>{t('description')}</CardDescription>
                </CardHeader>
                <CardContent>
                    <div className="animate-pulse space-y-3">
                        {[...Array(7)].map((_, i) => (
                            <div key={i} className="h-12 bg-gray-200 rounded"></div>
                        ))}
                    </div>
                </CardContent>
            </Card>
        );
    }

    if (!data || !data.breakdown || data.breakdown.length === 0) {
        return (
            <Card>
                <CardHeader>
                    <CardTitle>{t('title')}</CardTitle>
                    <CardDescription>{t('description')}</CardDescription>
                </CardHeader>
                <CardContent>
                    <p className="text-center py-8 text-gray-500">{t('noData')}</p>
                </CardContent>
            </Card>
        );
    }

    return (
        <Card>
            <CardHeader>
                <CardTitle>{t('title')}</CardTitle>
                <CardDescription>{t('description')}</CardDescription>
            </CardHeader>
            <CardContent>
                <div className="bg-white border rounded-lg overflow-hidden shadow-sm">
                    <Table>
                        <TableHeader>
                            <TableRow className="bg-gray-50">
                                <TableHead className="font-semibold">{t('columnDate')}</TableHead>
                                <TableHead className="font-semibold text-right">{t('columnUsage')}</TableHead>
                                <TableHead className="font-semibold text-right">{t('columnCost')}</TableHead>
                                <TableHead className="font-semibold text-right">{t('columnCalls')}</TableHead>
                            </TableRow>
                        </TableHeader>
                        <TableBody>
                            {data.breakdown.map((day) => (
                                <TableRow key={day.date}>
                                    <TableCell className="font-medium">
                                        {formatDate(day.date)}
                                    </TableCell>
                                    <TableCell className="text-right">
                                        {day.minutes.toFixed(1)}
                                    </TableCell>
                                    <TableCell className="text-right font-medium">
                                        ${(day.cost_usd || 0).toFixed(2)}
                                    </TableCell>
                                    <TableCell className="text-right">
                                        {day.call_count}
                                    </TableCell>
                                </TableRow>
                            ))}
                        </TableBody>
                        <TableFooter>
                            <TableRow className="bg-gray-50 font-semibold">
                                <TableCell>{t('total')}</TableCell>
                                <TableCell className="text-right">
                                    {data.total_minutes.toFixed(1)}
                                </TableCell>
                                <TableCell className="text-right">
                                    ${(data.total_cost_usd || 0).toFixed(2)}
                                </TableCell>
                                <TableCell className="text-right">
                                    {data.breakdown.reduce((sum, day) => sum + day.call_count, 0)}
                                </TableCell>
                            </TableRow>
                        </TableFooter>
                    </Table>
                </div>
            </CardContent>
        </Card>
    );
}
