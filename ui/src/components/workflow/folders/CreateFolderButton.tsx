'use client';

import { FolderPlus } from 'lucide-react';
import { useRouter } from 'next/navigation';
import { useTranslations } from 'next-intl';
import { useState } from 'react';
import { toast } from 'sonner';

import { createFolderApiV1FolderPost } from '@/client/sdk.gen';
import { Button } from '@/components/ui/button';

import { FolderFormDialog } from './FolderFormDialog';

export function CreateFolderButton() {
    const t = useTranslations('components.workflow.folders.createFolderButton');
    const router = useRouter();
    const [isOpen, setIsOpen] = useState(false);

    const handleCreate = async (name: string) => {
        const response = await createFolderApiV1FolderPost({ body: { name } });
        if (response.error) {
            // 409 = duplicate name; surface the server's message when present.
            const detail =
                (response.error as { detail?: string })?.detail ??
                t('createError');
            toast.error(detail);
            throw new Error(detail);
        }
        toast.success(t('createSuccess', { name }));
        router.refresh();
    };

    return (
        <>
            <Button variant="outline" onClick={() => setIsOpen(true)}>
                <FolderPlus className="w-4 h-4 mr-2" />
                {t('newFolder')}
            </Button>
            <FolderFormDialog
                open={isOpen}
                onOpenChange={setIsOpen}
                title={t('dialogTitle')}
                submitLabel={t('submitLabel')}
                onSubmit={handleCreate}
            />
        </>
    );
}
