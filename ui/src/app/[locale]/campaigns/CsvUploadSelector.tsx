'use client';

import { useTranslations } from 'next-intl';
import { useRef, useState } from 'react';
import { toast } from 'sonner';

import { getPresignedUploadUrlApiV1S3PresignedUploadUrlPost } from '@/client/sdk.gen';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Textarea } from '@/components/ui/textarea';
import logger from '@/lib/logger';

interface CsvUploadSelectorProps {
  onFileUploaded: (fileKey: string, fileName: string) => void;
  selectedFileName?: string;
}

const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

/**
 * Turn a manually-pasted caller list into CSV text the backend can ingest.
 *
 * Two accepted shapes:
 *  - A full CSV whose header row already contains `phone_number` → used as-is
 *    (lets power users include extra columns that become initial_context).
 *  - Otherwise each non-empty line is treated as a single phone number and a
 *    `phone_number` header is synthesised (the common "short list" case).
 */
function pastedTextToCsv(raw: string): string {
  const lines = raw
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter((l) => l.length > 0);

  if (lines.length === 0) return '';

  const firstCols = lines[0].toLowerCase().split(',').map((c) => c.trim());
  const hasHeader = firstCols.includes('phone_number');

  if (hasHeader) {
    return lines.join('\n');
  }

  return ['phone_number', ...lines].join('\n');
}

export default function CsvUploadSelector({ onFileUploaded, selectedFileName }: CsvUploadSelectorProps) {
  const t = useTranslations('components.csvUploadSelector');
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [pasteText, setPasteText] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Shared upload path: get a presigned URL, PUT the CSV bytes to S3/MinIO,
  // then hand the resulting file_key back to the parent. Used by both the file
  // picker and the manual paste box so the backend sees an identical source.
  const uploadCsv = async (file: Blob, fileName: string): Promise<boolean> => {
    setUploading(true);
    setUploadProgress(0);
    try {
      logger.info('Requesting presigned upload URL for:', fileName);
      const { data: presignedData, error } = await getPresignedUploadUrlApiV1S3PresignedUploadUrlPost({
        body: {
          file_name: fileName,
          file_size: file.size,
          content_type: 'text/csv',
        },
      });

      if (error || !presignedData) {
        throw new Error(t('getUploadUrlError'));
      }

      const uploadResponse = await fetch(presignedData.upload_url, {
        method: 'PUT',
        body: file,
        headers: {
          'Content-Type': 'text/csv',
        },
      });

      if (!uploadResponse.ok) {
        throw new Error(t('uploadToStorageError'));
      }

      setUploadProgress(100);
      logger.info('File uploaded successfully, file_key:', presignedData.file_key);
      onFileUploaded(presignedData.file_key, fileName);
      toast.success(t('fileUploadedSuccess', { fileName }));
      return true;
    } catch (error) {
      logger.error('Error uploading CSV:', error);
      toast.error(error instanceof Error ? error.message : t('uploadCsvError'));
      return false;
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  const handleFileSelect = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.name.endsWith('.csv')) {
      toast.error(t('selectCsvFileError'));
      return;
    }

    if (file.size > MAX_FILE_SIZE) {
      toast.error(t('fileSizeError'));
      return;
    }

    await uploadCsv(file, file.name);

    // Reset file input so re-selecting the same file fires onChange again.
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleButtonClick = () => {
    fileInputRef.current?.click();
  };

  const handleUsePastedList = async () => {
    const csv = pastedTextToCsv(pasteText);
    if (!csv) {
      toast.error(t('pasteEmptyError'));
      return;
    }

    const blob = new Blob([csv], { type: 'text/csv' });
    if (blob.size > MAX_FILE_SIZE) {
      toast.error(t('fileSizeError'));
      return;
    }

    const fileName = `manual-callers-${Date.now()}.csv`;
    const ok = await uploadCsv(blob, fileName);
    if (ok) {
      setPasteText('');
    }
  };

  return (
    <div className="space-y-2">
      <Label>{t('csvFileLabel')}</Label>
      <Tabs defaultValue="upload" className="w-full">
        <TabsList>
          <TabsTrigger value="upload">{t('tabUpload')}</TabsTrigger>
          <TabsTrigger value="paste">{t('tabPaste')}</TabsTrigger>
        </TabsList>

        <TabsContent value="upload" className="space-y-2">
          <div className="flex items-center gap-4">
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              onChange={handleFileSelect}
              className="hidden"
            />
            <Button
              type="button"
              variant="outline"
              onClick={handleButtonClick}
              disabled={uploading}
            >
              {uploading ? t('uploadingProgress', { progress: uploadProgress }) : t('uploadButton')}
            </Button>
            {selectedFileName && !uploading && (
              <div className="flex-1 text-sm">
                <span className="text-muted-foreground">{t('selectedLabel')} </span>
                <span className="text-primary">{selectedFileName}</span>
              </div>
            )}
          </div>
          <p className="text-sm text-muted-foreground">
            {t('helpText')} <br />
            {t('maxSize')}
          </p>
        </TabsContent>

        <TabsContent value="paste" className="space-y-2">
          <Textarea
            value={pasteText}
            onChange={(e) => setPasteText(e.target.value)}
            placeholder={t('pastePlaceholder')}
            rows={6}
            disabled={uploading}
            className="font-mono text-sm"
          />
          <div className="flex items-center gap-4">
            <Button
              type="button"
              variant="outline"
              onClick={handleUsePastedList}
              disabled={uploading || pasteText.trim().length === 0}
            >
              {uploading ? t('uploadingProgress', { progress: uploadProgress }) : t('pasteButton')}
            </Button>
            {selectedFileName && !uploading && (
              <div className="flex-1 text-sm">
                <span className="text-muted-foreground">{t('selectedLabel')} </span>
                <span className="text-primary">{selectedFileName}</span>
              </div>
            )}
          </div>
          <p className="text-sm text-muted-foreground">
            {t('pasteHelp')}
          </p>
        </TabsContent>
      </Tabs>
    </div>
  );
}
