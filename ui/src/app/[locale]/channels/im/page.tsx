'use client';

/**
 * IM Channels — Telegram management page.
 *
 * Phase 4b of the CliClaw merge. Backend: `api/routes/im_channels.py`
 * (Phase 4a). Bot loader: `telegram-bot/bot/channels.py` (Phase 4c).
 *
 * The page intentionally stays in one file (~250 lines) — small list +
 * create/edit dialog, no nested route tree. WhatsApp and Discord tabs
 * are deliberately greyed-out placeholders per `.claude/goals/04-ui-channels.md`.
 */

import { useTranslations } from 'next-intl';
import { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { useAuth } from '@/lib/auth';
import {
  createTelegramChannel,
  createWhatsAppChannel,
  deleteTelegramChannel,
  deleteWhatsAppChannel,
  ImChannelsApiError,
  listTelegramChannels,
  listWhatsAppChannels,
  TelegramChannel,
  testTelegramChannel,
  testWhatsAppChannel,
  updateTelegramChannel,
  updateWhatsAppChannel,
  WhatsAppChannel,
  whatsappWebhookUrl,
} from '@/lib/imChannels';

export default function IMChannelsPage() {
  const t = useTranslations('pages.channels.im');
  const { user, getAccessToken, loading: authLoading, redirectToLogin } = useAuth();
  const hasFetched = useRef(false);

  // Route a 401 from any IM channels API call straight to the login page.
  // Without this, the catch handlers below toast a generic "Failed to
  // load channels" message and leave the page on its empty-state
  // placeholder — which makes an expired JWT look identical to "you
  // haven't registered any bots", which is confusing.
  const handleApiError = (err: unknown, fallbackMessage: string) => {
    if (err instanceof ImChannelsApiError && err.status === 401) {
      redirectToLogin();
      return;
    }
    toast.error(err instanceof Error ? err.message : fallbackMessage);
  };

  const [channels, setChannels] = useState<TelegramChannel[]>([]);
  const [waChannels, setWaChannels] = useState<WhatsAppChannel[]>([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [waDialogOpen, setWaDialogOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<'telegram' | 'whatsapp' | 'discord'>(
    'telegram',
  );

  const refresh = async () => {
    try {
      setLoading(true);
      const token = await getAccessToken();
      const [rows, waRows] = await Promise.all([
        listTelegramChannels(token),
        listWhatsAppChannels(token).catch(() => [] as WhatsAppChannel[]),
      ]);
      setChannels(rows);
      setWaChannels(waRows);
    } catch (err) {
      handleApiError(err, t('toastLoadFailed'));
    } finally {
      setLoading(false);
    }
  };

  const onWaToggle = async (ch: WhatsAppChannel) => {
    try {
      const token = await getAccessToken();
      const updated = await updateWhatsAppChannel(token, ch.id, { enabled: !ch.enabled });
      setWaChannels((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
      toast.success(
        updated.enabled
          ? t('toastEnabled', { name: updated.name })
          : t('toastDisabled', { name: updated.name }),
      );
    } catch (err) {
      handleApiError(err, t('toastToggleFailed'));
    }
  };

  const onWaTest = async (ch: WhatsAppChannel) => {
    try {
      const token = await getAccessToken();
      const result = await testWhatsAppChannel(token, ch.id);
      if (result.ok) {
        toast.success(
          t('toastConnectedWa', {
            name: result.verified_name ?? t('valueUnknown'),
            phone: result.phone_number ?? t('valueNoNumber'),
          }),
        );
      } else {
        toast.error(t('toastTestFailed', { error: result.error ?? t('valueUnknownError') }));
      }
    } catch (err) {
      handleApiError(err, t('toastTestRequestFailed'));
    }
  };

  const onWaDelete = async (ch: WhatsAppChannel) => {
    if (!confirm(t('confirmDeleteWa', { name: ch.name }))) return;
    try {
      const token = await getAccessToken();
      await deleteWhatsAppChannel(token, ch.id);
      setWaChannels((prev) => prev.filter((c) => c.id !== ch.id));
      toast.success(t('toastDeleted', { name: ch.name }));
    } catch (err) {
      handleApiError(err, t('toastDeleteFailed'));
    }
  };

  useEffect(() => {
    if (authLoading || !user || hasFetched.current) return;
    hasFetched.current = true;
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authLoading, user]);

  const onToggle = async (ch: TelegramChannel) => {
    try {
      const token = await getAccessToken();
      const updated = await updateTelegramChannel(token, ch.id, {
        enabled: !ch.enabled,
      });
      setChannels((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
      toast.success(
        updated.enabled
          ? t('toastEnabled', { name: updated.name })
          : t('toastDisabled', { name: updated.name }),
      );
    } catch (err) {
      handleApiError(err, t('toastToggleFailed'));
    }
  };

  const onTest = async (ch: TelegramChannel) => {
    try {
      const token = await getAccessToken();
      const result = await testTelegramChannel(token, ch.id);
      if (result.ok) {
        toast.success(t('toastConnectedTelegram', { username: result.username ?? t('valueUnknown') }));
      } else {
        toast.error(t('toastTestFailed', { error: result.error ?? t('valueUnknownError') }));
      }
    } catch (err) {
      handleApiError(err, t('toastTestRequestFailed'));
    }
  };

  const onDelete = async (ch: TelegramChannel) => {
    if (!confirm(t('confirmDeleteTelegram', { name: ch.name }))) return;
    try {
      const token = await getAccessToken();
      await deleteTelegramChannel(token, ch.id);
      setChannels((prev) => prev.filter((c) => c.id !== ch.id));
      toast.success(t('toastDeleted', { name: ch.name }));
    } catch (err) {
      handleApiError(err, t('toastDeleteFailed'));
    }
  };

  return (
    <div className="container mx-auto py-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">{t('title')}</h1>
          <p className="text-sm text-muted-foreground">{t('subtitle')}</p>
        </div>
        {activeTab === 'telegram' && (
          <Button onClick={() => setDialogOpen(true)}>{t('addTelegramBot')}</Button>
        )}
        {activeTab === 'whatsapp' && (
          <Button onClick={() => setWaDialogOpen(true)}>{t('addWhatsAppNumber')}</Button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b">
        {(['telegram', 'whatsapp', 'discord'] as const).map((tab) => {
          const isLive = tab === 'telegram' || tab === 'whatsapp';
          return (
            <button
              key={tab}
              type="button"
              onClick={() => isLive && setActiveTab(tab)}
              className={[
                'px-3 py-2 text-sm capitalize border-b-2 -mb-px',
                activeTab === tab ? 'border-primary text-primary' : 'border-transparent',
                !isLive
                  ? 'opacity-50 cursor-not-allowed'
                  : 'cursor-pointer hover:text-primary',
              ].join(' ')}
              disabled={!isLive}
              title={!isLive ? t('comingSoon') : undefined}
            >
              {t(`tab_${tab}`)}
              {!isLive ? t('soonSuffix') : ''}
            </button>
          );
        })}
      </div>

      {/* List */}
      {activeTab === 'telegram' &&
        (loading ? (
          <p className="text-sm text-muted-foreground">{t('loading')}</p>
        ) : channels.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {t.rich('emptyTelegram', { em: (c) => <em>{c}</em> })}
          </p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {channels.map((ch) => (
              <Card key={ch.id}>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-base">{ch.name}</CardTitle>
                  <Switch
                    checked={ch.enabled}
                    onCheckedChange={() => onToggle(ch)}
                  />
                </CardHeader>
                <CardContent className="text-sm space-y-2">
                  <div className="text-muted-foreground">
                    {t('labelToken')} <code>{ch.config.bot_token || t('valueEmpty')}</code>
                  </div>
                  <div className="text-muted-foreground">
                    {t('labelAllowedUsers')}{' '}
                    {ch.config.allowed_user_ids && ch.config.allowed_user_ids.length > 0
                      ? ch.config.allowed_user_ids.join(', ')
                      : t('valueAll')}
                  </div>
                  <div className="flex gap-2 pt-2">
                    <Button size="sm" variant="outline" onClick={() => onTest(ch)}>
                      {t('testConnection')}
                    </Button>
                    <Button size="sm" variant="destructive" onClick={() => onDelete(ch)}>
                      {t('delete')}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        ))}

      {activeTab === 'whatsapp' &&
        (loading ? (
          <p className="text-sm text-muted-foreground">{t('loading')}</p>
        ) : waChannels.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            {t.rich('emptyWhatsApp', { em: (c) => <em>{c}</em> })}
          </p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {waChannels.map((ch) => (
              <Card key={ch.id}>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-base">{ch.name}</CardTitle>
                  <Switch
                    checked={ch.enabled}
                    onCheckedChange={() => onWaToggle(ch)}
                  />
                </CardHeader>
                <CardContent className="text-sm space-y-2">
                  <div className="text-muted-foreground">
                    {t('labelPhoneNumberId')} <code>{ch.config.phone_number_id || t('valueEmpty')}</code>
                  </div>
                  {ch.config.business_account_id && (
                    <div className="text-muted-foreground">
                      {t('labelWabaId')} <code>{ch.config.business_account_id}</code>
                    </div>
                  )}
                  <div className="text-muted-foreground">
                    {t('labelGraphVersion')}{' '}
                    <code>{ch.config.graph_version || 'v20.0'}</code>
                  </div>
                  <div className="text-muted-foreground break-all">
                    {t('labelWebhookUrl')}{' '}
                    <code className="text-xs">{whatsappWebhookUrl(ch.id)}</code>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {t.rich('webhookHelp', { em: (c) => <em>{c}</em> })}
                  </p>
                  <div className="flex gap-2 pt-2">
                    <Button size="sm" variant="outline" onClick={() => onWaTest(ch)}>
                      {t('testConnection')}
                    </Button>
                    <Button size="sm" variant="destructive" onClick={() => onWaDelete(ch)}>
                      {t('delete')}
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        ))}

      <CreateTelegramDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        onCreated={(ch) => {
          setChannels((prev) => [...prev, ch]);
          setDialogOpen(false);
        }}
      />
      <CreateWhatsAppDialog
        open={waDialogOpen}
        onOpenChange={setWaDialogOpen}
        onCreated={(ch) => {
          setWaChannels((prev) => [...prev, ch]);
          setWaDialogOpen(false);
        }}
      />
    </div>
  );
}

function CreateTelegramDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onCreated: (ch: TelegramChannel) => void;
}) {
  const t = useTranslations('pages.channels.im');
  const { getAccessToken, redirectToLogin } = useAuth();
  const [name, setName] = useState('');
  const [token, setToken] = useState('');
  const [allowed, setAllowed] = useState('');
  const [enabled, setEnabled] = useState(true);
  const [saving, setSaving] = useState(false);

  const reset = () => {
    setName('');
    setToken('');
    setAllowed('');
    setEnabled(true);
  };

  const save = async () => {
    if (!name.trim() || !token.trim()) {
      toast.error(t('errorTelegramRequired'));
      return;
    }
    setSaving(true);
    try {
      const jwt = await getAccessToken();
      const allowedIds = allowed
        .split(',')
        .map((s) => parseInt(s.trim(), 10))
        .filter((n) => Number.isFinite(n));
      const created = await createTelegramChannel(jwt, {
        name: name.trim(),
        bot_token: token.trim(),
        allowed_user_ids: allowedIds,
        enabled,
      });
      toast.success(t('toastTelegramCreated', { name: created.name }));
      // Best-effort surface: show the raw api_key once via a toast. Operator
      // can rotate later via the (planned) rotate-api-key control.
      toast(t('toastApiKey', { key: created.api_key }), { duration: 20000 });
      onCreated(created);
      reset();
    } catch (err) {
      if (err instanceof ImChannelsApiError && err.status === 401) {
        redirectToLogin();
        return;
      }
      toast.error(err instanceof Error ? err.message : t('toastCreateFailed'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t('dialogTelegramTitle')}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <div className="space-y-1">
            <Label htmlFor="name">{t('fieldName')}</Label>
            <Input
              id="name"
              placeholder="ops-bot"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="token">{t('fieldBotToken')}</Label>
            <Input
              id="token"
              type="password"
              placeholder="123456789:ABC…"
              value={token}
              onChange={(e) => setToken(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">{t('hintBotToken')}</p>
          </div>
          <div className="space-y-1">
            <Label htmlFor="allowed">{t('fieldAllowedUserIds')}</Label>
            <Input
              id="allowed"
              placeholder="e.g. 123456789, 987654321"
              value={allowed}
              onChange={(e) => setAllowed(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">{t('hintAllowedUserIds')}</p>
          </div>
          <div className="flex items-center gap-2">
            <Switch checked={enabled} onCheckedChange={setEnabled} id="enabled" />
            <Label htmlFor="enabled">{t('fieldEnabled')}</Label>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            {t('cancel')}
          </Button>
          <Button onClick={save} disabled={saving}>
            {saving ? t('saving') : t('save')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function CreateWhatsAppDialog({
  open,
  onOpenChange,
  onCreated,
}: {
  open: boolean;
  onOpenChange: (v: boolean) => void;
  onCreated: (ch: WhatsAppChannel) => void;
}) {
  const t = useTranslations('pages.channels.im');
  const { getAccessToken, redirectToLogin } = useAuth();
  const [name, setName] = useState('');
  const [phoneNumberId, setPhoneNumberId] = useState('');
  const [accessToken, setAccessToken] = useState('');
  const [appSecret, setAppSecret] = useState('');
  const [verifyToken, setVerifyToken] = useState('');
  const [businessAccountId, setBusinessAccountId] = useState('');
  const [graphVersion, setGraphVersion] = useState('v20.0');
  const [enabled, setEnabled] = useState(true);
  const [saving, setSaving] = useState(false);

  const reset = () => {
    setName('');
    setPhoneNumberId('');
    setAccessToken('');
    setAppSecret('');
    setVerifyToken('');
    setBusinessAccountId('');
    setGraphVersion('v20.0');
    setEnabled(true);
  };

  const generateVerifyToken = () => {
    // 32 hex chars from crypto.getRandomValues — operator can also paste
    // their own. Stored encrypted server-side; only shown in plaintext
    // here (to copy into Meta Developer Console).
    const bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
    setVerifyToken(hex);
  };

  const save = async () => {
    if (!name.trim() || !phoneNumberId.trim() || !accessToken.trim() ||
        !appSecret.trim() || !verifyToken.trim()) {
      toast.error(t('errorWhatsAppRequired'));
      return;
    }
    setSaving(true);
    try {
      const jwt = await getAccessToken();
      const created = await createWhatsAppChannel(jwt, {
        name: name.trim(),
        phone_number_id: phoneNumberId.trim(),
        access_token: accessToken.trim(),
        app_secret: appSecret.trim(),
        verify_token: verifyToken.trim(),
        business_account_id: businessAccountId.trim() || undefined,
        graph_version: graphVersion.trim() || 'v20.0',
        enabled,
      });
      toast.success(t('toastWhatsAppCreated', { name: created.name }));
      onCreated(created);
      reset();
    } catch (err) {
      if (err instanceof ImChannelsApiError && err.status === 401) {
        redirectToLogin();
        return;
      }
      toast.error(err instanceof Error ? err.message : t('toastCreateFailed'));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t('dialogWhatsAppTitle')}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2 max-h-[60vh] overflow-y-auto">
          <div className="space-y-1">
            <Label htmlFor="wa-name">{t('fieldDisplayName')}</Label>
            <Input
              id="wa-name"
              placeholder="support-line"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">{t('hintDisplayName')}</p>
          </div>
          <div className="space-y-1">
            <Label htmlFor="wa-pnid">{t('fieldPhoneNumberId')}</Label>
            <Input
              id="wa-pnid"
              placeholder="123456789012345"
              value={phoneNumberId}
              onChange={(e) => setPhoneNumberId(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">{t('hintPhoneNumberId')}</p>
          </div>
          <div className="space-y-1">
            <Label htmlFor="wa-token">{t('fieldAccessToken')}</Label>
            <Input
              id="wa-token"
              type="password"
              placeholder="EAA…"
              value={accessToken}
              onChange={(e) => setAccessToken(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">{t('hintAccessToken')}</p>
          </div>
          <div className="space-y-1">
            <Label htmlFor="wa-app-secret">{t('fieldAppSecret')}</Label>
            <Input
              id="wa-app-secret"
              type="password"
              placeholder={t('placeholderAppSecret')}
              value={appSecret}
              onChange={(e) => setAppSecret(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              {t.rich('hintAppSecret', { code: (c) => <code>{c}</code> })}
            </p>
          </div>
          <div className="space-y-1">
            <Label htmlFor="wa-verify">{t('fieldVerifyToken')}</Label>
            <div className="flex gap-2">
              <Input
                id="wa-verify"
                placeholder={t('placeholderVerifyToken')}
                value={verifyToken}
                onChange={(e) => setVerifyToken(e.target.value)}
              />
              <Button type="button" variant="outline" onClick={generateVerifyToken}>
                {t('generate')}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">{t('hintVerifyToken')}</p>
          </div>
          <div className="space-y-1">
            <Label htmlFor="wa-waba">{t('fieldBusinessAccountId')}</Label>
            <Input
              id="wa-waba"
              placeholder="123456789012345"
              value={businessAccountId}
              onChange={(e) => setBusinessAccountId(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="wa-graph">{t('fieldGraphVersion')}</Label>
            <Input
              id="wa-graph"
              placeholder="v20.0"
              value={graphVersion}
              onChange={(e) => setGraphVersion(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-2">
            <Switch checked={enabled} onCheckedChange={setEnabled} id="wa-enabled" />
            <Label htmlFor="wa-enabled">{t('fieldEnabled')}</Label>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            {t('cancel')}
          </Button>
          <Button onClick={save} disabled={saving}>
            {saving ? t('saving') : t('save')}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
