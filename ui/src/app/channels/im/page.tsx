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
  const { user, getAccessToken, loading: authLoading } = useAuth();
  const hasFetched = useRef(false);

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
      toast.error(err instanceof Error ? err.message : 'Failed to load channels');
    } finally {
      setLoading(false);
    }
  };

  const onWaToggle = async (ch: WhatsAppChannel) => {
    try {
      const token = await getAccessToken();
      const updated = await updateWhatsAppChannel(token, ch.id, { enabled: !ch.enabled });
      setWaChannels((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
      toast.success(`${updated.name} ${updated.enabled ? 'enabled' : 'disabled'}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Toggle failed');
    }
  };

  const onWaTest = async (ch: WhatsAppChannel) => {
    try {
      const token = await getAccessToken();
      const result = await testWhatsAppChannel(token, ch.id);
      if (result.ok) {
        toast.success(
          `Connected as ${result.verified_name ?? 'unknown'} (${result.phone_number ?? 'no number'})`,
        );
      } else {
        toast.error(`Test failed: ${result.error ?? 'unknown error'}`);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Test request failed');
    }
  };

  const onWaDelete = async (ch: WhatsAppChannel) => {
    if (!confirm(`Delete WhatsApp channel "${ch.name}"?`)) return;
    try {
      const token = await getAccessToken();
      await deleteWhatsAppChannel(token, ch.id);
      setWaChannels((prev) => prev.filter((c) => c.id !== ch.id));
      toast.success(`Deleted ${ch.name}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Delete failed');
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
      toast.success(`${updated.name} ${updated.enabled ? 'enabled' : 'disabled'}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Toggle failed');
    }
  };

  const onTest = async (ch: TelegramChannel) => {
    try {
      const token = await getAccessToken();
      const result = await testTelegramChannel(token, ch.id);
      if (result.ok) {
        toast.success(`Connected as @${result.username ?? 'unknown'}`);
      } else {
        toast.error(`Test failed: ${result.error ?? 'unknown error'}`);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Test request failed');
    }
  };

  const onDelete = async (ch: TelegramChannel) => {
    if (!confirm(`Delete channel "${ch.name}"? The bot will stop polling.`)) return;
    try {
      const token = await getAccessToken();
      await deleteTelegramChannel(token, ch.id);
      setChannels((prev) => prev.filter((c) => c.id !== ch.id));
      toast.success(`Deleted ${ch.name}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Delete failed');
    }
  };

  return (
    <div className="container mx-auto py-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">IM Channels</h1>
          <p className="text-sm text-muted-foreground">
            Manage messaging-platform integrations. Tokens are stored encrypted;
            the bot picks them up automatically via Redis hot-reload.
          </p>
        </div>
        {activeTab === 'telegram' && (
          <Button onClick={() => setDialogOpen(true)}>+ Add Telegram bot</Button>
        )}
        {activeTab === 'whatsapp' && (
          <Button onClick={() => setWaDialogOpen(true)}>+ Add WhatsApp number</Button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b">
        {(['telegram', 'whatsapp', 'discord'] as const).map((t) => {
          const isLive = t === 'telegram' || t === 'whatsapp';
          return (
            <button
              key={t}
              type="button"
              onClick={() => isLive && setActiveTab(t)}
              className={[
                'px-3 py-2 text-sm capitalize border-b-2 -mb-px',
                activeTab === t ? 'border-primary text-primary' : 'border-transparent',
                !isLive
                  ? 'opacity-50 cursor-not-allowed'
                  : 'cursor-pointer hover:text-primary',
              ].join(' ')}
              disabled={!isLive}
              title={!isLive ? 'Coming soon' : undefined}
            >
              {t}
              {!isLive ? ' (soon)' : ''}
            </button>
          );
        })}
      </div>

      {/* List */}
      {activeTab === 'telegram' &&
        (loading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : channels.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No Telegram bots registered yet. Click <em>Add Telegram bot</em> to start.
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
                    Token: <code>{ch.config.bot_token || '(empty)'}</code>
                  </div>
                  <div className="text-muted-foreground">
                    Allowed users:{' '}
                    {ch.config.allowed_user_ids && ch.config.allowed_user_ids.length > 0
                      ? ch.config.allowed_user_ids.join(', ')
                      : 'all'}
                  </div>
                  <div className="flex gap-2 pt-2">
                    <Button size="sm" variant="outline" onClick={() => onTest(ch)}>
                      Test connection
                    </Button>
                    <Button size="sm" variant="destructive" onClick={() => onDelete(ch)}>
                      Delete
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        ))}

      {activeTab === 'whatsapp' &&
        (loading ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : waChannels.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            No WhatsApp numbers registered yet. Click <em>Add WhatsApp number</em> to
            connect one via the Meta Cloud API.
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
                    Phone number id: <code>{ch.config.phone_number_id || '(empty)'}</code>
                  </div>
                  {ch.config.business_account_id && (
                    <div className="text-muted-foreground">
                      WABA id: <code>{ch.config.business_account_id}</code>
                    </div>
                  )}
                  <div className="text-muted-foreground">
                    Graph version:{' '}
                    <code>{ch.config.graph_version || 'v20.0'}</code>
                  </div>
                  <div className="text-muted-foreground break-all">
                    Webhook URL:{' '}
                    <code className="text-xs">{whatsappWebhookUrl(ch.id)}</code>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    Paste the webhook URL + the channel&apos;s verify token into the Meta
                    Developer Console under <em>WhatsApp → Configuration → Webhook</em>,
                    then click <em>Verify and save</em>.
                  </p>
                  <div className="flex gap-2 pt-2">
                    <Button size="sm" variant="outline" onClick={() => onWaTest(ch)}>
                      Test connection
                    </Button>
                    <Button size="sm" variant="destructive" onClick={() => onWaDelete(ch)}>
                      Delete
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
  const { getAccessToken } = useAuth();
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
      toast.error('Name and bot token are required');
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
      toast.success(`Created "${created.name}". API key minted (shown once below).`);
      // Best-effort surface: show the raw api_key once via a toast. Operator
      // can rotate later via the (planned) rotate-api-key control.
      toast(`API key: ${created.api_key}`, { duration: 20000 });
      onCreated(created);
      reset();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Create failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add a Telegram bot</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2">
          <div className="space-y-1">
            <Label htmlFor="name">Name</Label>
            <Input
              id="name"
              placeholder="ops-bot"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="token">Bot token</Label>
            <Input
              id="token"
              type="password"
              placeholder="123456789:ABC…"
              value={token}
              onChange={(e) => setToken(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              From @BotFather. Stored encrypted; only the last 6 chars shown after save.
            </p>
          </div>
          <div className="space-y-1">
            <Label htmlFor="allowed">Allowed Telegram user IDs (comma-separated)</Label>
            <Input
              id="allowed"
              placeholder="e.g. 123456789, 987654321"
              value={allowed}
              onChange={(e) => setAllowed(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Empty = anyone who messages the bot can use it.
            </p>
          </div>
          <div className="flex items-center gap-2">
            <Switch checked={enabled} onCheckedChange={setEnabled} id="enabled" />
            <Label htmlFor="enabled">Enabled</Label>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={save} disabled={saving}>
            {saving ? 'Saving…' : 'Save'}
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
  const { getAccessToken } = useAuth();
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
      toast.error('Name, phone number id, access token, app secret, and verify token are required');
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
      toast.success(`Created "${created.name}". Configure the webhook URL in Meta Developer Console.`);
      onCreated(created);
      reset();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Create failed');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add a WhatsApp number</DialogTitle>
        </DialogHeader>
        <div className="space-y-3 py-2 max-h-[60vh] overflow-y-auto">
          <div className="space-y-1">
            <Label htmlFor="wa-name">Display name</Label>
            <Input
              id="wa-name"
              placeholder="support-line"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Internal label only — not shown to WhatsApp users.
            </p>
          </div>
          <div className="space-y-1">
            <Label htmlFor="wa-pnid">Phone number id</Label>
            <Input
              id="wa-pnid"
              placeholder="123456789012345"
              value={phoneNumberId}
              onChange={(e) => setPhoneNumberId(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              From Meta Business Manager → WhatsApp → API Setup.
            </p>
          </div>
          <div className="space-y-1">
            <Label htmlFor="wa-token">Access token</Label>
            <Input
              id="wa-token"
              type="password"
              placeholder="EAA…"
              value={accessToken}
              onChange={(e) => setAccessToken(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Long-lived system-user token. Stored encrypted; only the last 6 chars
              shown after save.
            </p>
          </div>
          <div className="space-y-1">
            <Label htmlFor="wa-app-secret">App secret</Label>
            <Input
              id="wa-app-secret"
              type="password"
              placeholder="The Meta App Secret"
              value={appSecret}
              onChange={(e) => setAppSecret(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Used to verify the <code>X-Hub-Signature-256</code> header on inbound
              webhooks. Found under Meta Developer Console → App Settings → Basic.
            </p>
          </div>
          <div className="space-y-1">
            <Label htmlFor="wa-verify">Webhook verify token</Label>
            <div className="flex gap-2">
              <Input
                id="wa-verify"
                placeholder="Any opaque secret you choose"
                value={verifyToken}
                onChange={(e) => setVerifyToken(e.target.value)}
              />
              <Button type="button" variant="outline" onClick={generateVerifyToken}>
                Generate
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Paste this verbatim into Meta&apos;s webhook subscription form.
              Stored encrypted; only the last 6 chars shown after save.
            </p>
          </div>
          <div className="space-y-1">
            <Label htmlFor="wa-waba">Business account id (optional)</Label>
            <Input
              id="wa-waba"
              placeholder="123456789012345"
              value={businessAccountId}
              onChange={(e) => setBusinessAccountId(e.target.value)}
            />
          </div>
          <div className="space-y-1">
            <Label htmlFor="wa-graph">Graph API version</Label>
            <Input
              id="wa-graph"
              placeholder="v20.0"
              value={graphVersion}
              onChange={(e) => setGraphVersion(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-2">
            <Switch checked={enabled} onCheckedChange={setEnabled} id="wa-enabled" />
            <Label htmlFor="wa-enabled">Enabled</Label>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={save} disabled={saving}>
            {saving ? 'Saving…' : 'Save'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
