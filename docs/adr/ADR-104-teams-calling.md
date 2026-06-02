# ADR-104 — Microsoft Teams calling integration

**Status:** Proposed
**Date:** 2026-06-02
**Context:** Request to integrate Microsoft Teams for outbound (and if possible
inbound) AI voice calls, originally framed as "add it to IM Channels". After
mapping the IM-channels and telephony subsystems, this ADR records *where* Teams
calling belongs, the hard media constraint that shapes the whole design, the
media-path options considered, and the recommended architecture mapped onto the
existing telephony provider abstraction.

## Decision

**Build Teams *calling* as a telephony provider (`api/services/telephony/providers/teams/`), not an IM channel — and bridge media through Azure Communication Services (ACS) Call Automation rather than the raw Microsoft Graph calling API.**

Two decisions in one:

1. **Calling is telephony, not IM Channels.** IM Channels (Telegram, WhatsApp)
   are asynchronous *text* dispatchers — no real-time audio, no call state
   machine, no media transport. Teams voice calls need bidirectional real-time
   PCM into the pipecat pipeline (STT in ← caller, TTS out → caller), exactly
   like Twilio/Telnyx/Vonage. So it implements `TelephonyProvider`
   (`api/services/telephony/base.py:59`) and registers via `ProviderSpec`
   (`api/services/telephony/registry.py`), mirroring the **Telnyx** provider
   (REST call-control + WebSocket media streaming + event webhooks + on-save
   auto-provisioning). Teams *text chat*, if ever wanted, is a separate IM
   channel and out of scope here.

2. **Media via ACS Call Automation, with Teams interop.** ACS Call Automation
   exposes **bidirectional audio streaming over a WebSocket** (16-bit PCM,
   16 kHz mono) reachable from any backend incl. Python, plus REST call-control
   and event callbacks — structurally identical to the Telnyx provider. ACS
   natively interoperates with Teams: it can **call a Teams user**
   (`MicrosoftTeamsUserIdentifier`) and **join a Teams meeting** (meeting join
   URL). The provider is named `teams` (the config discriminator); the
   ACS/Teams-interop specifics live in its credentials/config.

## Why not the raw Microsoft Graph calling API

Dograh's pipeline needs raw bidirectional PCM over a WebSocket into pipecat.
Microsoft Graph's calling API offers two media modes, **neither of which
delivers that to a Python backend**:

| Graph media mode | Raw bidirectional audio? | Python-usable? | Verdict |
|---|---|---|---|
| **Application-hosted media** | Yes (raw RTP) | **No — .NET/Windows only** (native C++ media stack via `Microsoft.Graph.Communications.Calls.Media`) | Not viable from FastAPI/Python without a separate .NET media-bot |
| **Service-hosted media** | No — only `playPrompt` / `record` / DTMF (`subscribeToTone`) | Yes | IVR-only; cannot stream live AI audio |

i.e. **"pure Graph API" cannot drive a real-time conversational AI call from
Python.** Application-hosted media is the only Graph mode with raw audio, and it
is a Windows/.NET-only native media stack. This constraint is the single biggest
driver of the decision.

## Media-path options considered

### Option ① — ACS Call Automation + Teams interop (CHOSEN)

ACS Call Automation REST creates the call; `mediaStreaming` points ACS at a
`wss://` transport on our backend; ACS streams PCM both ways; ACS posts call
events to a `callbackUri`. The WebSocket plugs into a pipecat
`FastAPIWebsocketTransport` via a new `AcsFrameSerializer`. Teams is reached via
ACS interop (call Teams users, join Teams meetings).

- **Pros:** fits the existing telephony abstraction almost 1:1 (it *is* the
  Telnyx shape with different field names); Python-native; outbound and
  meeting-join both feasible; reuses the pipecat WebSocket transport path.
- **Cons:** requires an Azure ACS resource (Azure billing); "Teams" is reached
  via ACS interop, not raw Graph.

### Option ② — Teams Direct Routing → Asterisk SBC

Terminate Teams Phone **Direct Routing** SIP at the Asterisk we already run
(ARI + AudioSocket; see ADR-101) and reuse the `ari` audio path. Graph used only
for optional click-to-call signaling.

- **Pros:** leverages existing infra (Asterisk, SIP providers 3CX/MessageNet);
  no ACS.
- **Cons:** telecom-ops heavy (certified SBC, SIP trunk, Teams Phone licensing);
  Asterisk is not a Microsoft-certified SBC (fine for lab, friction for prod).

### Option ③ — Pure Graph + a .NET media-bot sidecar

A small .NET service using the Graph Communications Media SDK bridges raw Teams
media ↔ Dograh over WebSocket/AudioSocket.

- **Pros:** "real" Graph calling, full Teams feature set.
- **Cons:** an entire second runtime/language to build, deploy, and maintain;
  highest effort and operational surface.

## Architecture (Option ①)

New package mirroring `providers/telnyx/`:

```
api/services/telephony/providers/teams/
  __init__.py     # ProviderSpec + register(); on-save: register ACS Event Grid / callback URI
  provider.py     # TeamsProvider(TelephonyProvider)
  transport.py    # create_transport() -> FastAPIWebsocketTransport(serializer=AcsFrameSerializer, sample_rate=16000)
  serializers.py  # AcsFrameSerializer: ACS WS media frames <-> pipecat AudioRawFrame
  config.py       # TeamsConfigurationRequest / TeamsConfigurationResponse (pydantic, masked)
  routes.py       # ACS event callbacks (CallConnected/Disconnected/…) + media WebSocket
```

Implements the `TelephonyProvider` ABC: `initiate_call`, `get_call_status`,
`validate_config`, `verify_inbound_signature`, `parse_status_callback`,
`handle_websocket`, `can_handle_webhook`, `parse_inbound_webhook`,
`transfer_call`, `supports_transfers`.

`ProviderSpec` registration (one `register(...)` at import, like
`providers/telnyx/__init__.py`):

- `name="teams"`, `provider_cls=TeamsProvider`
- `transport_factory=create_transport`, `transport_sample_rate=16000`
  (ACS bidirectional streaming = 16-bit PCM 16 kHz mono)
- `config_request_cls` / `config_response_cls` (masked)
- `account_id_credential_field="acs_resource_id"` — so inbound webhooks resolve
  to the right org config (`factory.py` `get_telephony_provider_for_inbound`)
- `preprocess_credentials_on_save` — register the ACS Event Grid subscription /
  callback URI (mirrors Telnyx's `_ensure_connection_id`)

Credentials live in `TelephonyConfigurationModel.credentials` (JSONB) like every
provider. **Caveat:** telephony creds are stored *plaintext* today (unlike IM
Channels' Fernet). Teams creds include an Azure AD **client secret**, so this ADR
recommends encrypting them — a deliberate deviation from the current norm (see
Open questions).

### Outbound flow (MVP)

```
UI "test call" / campaign
  -> POST /api/v1/telephony/initiate-call            (existing, routes/telephony.py:72)
  -> factory resolves TeamsProvider
  -> TeamsProvider.initiate_call(target, webhook_url, run_id, ...):
       - acquire AAD app token (client-credentials, cached)
       - POST ACS Call Automation create-call:
            target = MicrosoftTeamsUser(teamsUserId) | Teams meeting join URL | PSTN number
            mediaStreaming = { transportUrl: wss://<backend>/api/v1/telephony/ws?...run_id,
                               audioFormat: pcm16k }
            callbackUri = https://<backend>/api/v1/telephony/teams/events/<run_id>
       - return CallInitiationResult(call_id, status, ...)
  -> ACS rings target; on answer opens the media WS
  -> routes.py media WS -> provider.handle_websocket() -> create_transport()
       -> FastAPIWebsocketTransport(AcsFrameSerializer) -> pipecat pipeline (STT->LLM->TTS)
  -> ACS posts call events to callbackUri -> parse_status_callback() updates WorkflowRun
```

This is the Telnyx flow with ACS field names (`stream_url`/`webhook_url` ->
ACS `transportUrl`/`callbackUri`).

### Inbound flow (later phase — harder)

Inbound ("a Teams user / PSTN number calls the bot") requires the bot to own a
callable identity: an ACS-provisioned phone number (PSTN inbound) or a Teams
resource account / auto-attendant routing to ACS. ACS raises an `IncomingCall`
Event Grid event → `routes.py` answers via Call Automation with the same
`mediaStreaming` block → identical audio path. Feasible but needs number /
resource-account provisioning + Event Grid wiring, so it is a distinct phase, not
free with outbound.

## Auth & Azure prerequisites (operator-provided)

- **Azure AD app registration** (client ID + secret + tenant ID) with
  *application* permissions for ACS Call Automation; for direct Teams-user
  calling, Graph `Calls.*` application permissions + tenant admin consent.
- **An ACS resource** (Azure subscription) — calling endpoint, media streaming,
  and (for inbound) phone numbers.
- **Teams interop** enabled on the tenant; meeting-join needs the meeting URL;
  calling Teams users needs the interop policy + user object IDs.
- Token handling: client-credentials flow, cached with refresh; secret stored
  in the provider config (encrypted — see Open questions).

## UI

Add a "Microsoft Teams" provider to the existing telephony-config UI, driven by
`ui_metadata` on the `ProviderSpec` and surfaced via
`GET /api/v1/telephony/providers/metadata`. Fields: tenant ID, client ID, client
secret, ACS connection string / resource ID, default target type (Teams user /
meeting / PSTN). No bespoke page — it rides the existing
telephony-configurations screen (unlike IM Channels, which needs its own tab).

## Phasing

| Phase | Deliverable | Effort |
|---|---|---|
| 0 | Azure setup (app reg, ACS resource, admin consent) — operator side | external |
| 1 — MVP | `teams` provider: **outbound** to a Teams user / meeting-join, full AI audio via ACS WS streaming, call events, UI config | Large (new provider + new serializer + AAD auth) |
| 2 | **Inbound** (ACS number / resource account + Event Grid `IncomingCall`) | Medium-Large |
| 3 | Transfers (`transfer_call`), recording, DTMF, cost tracking (ties into the Paygent aggregator) | Medium |

## Open questions

1. **Media path** — proceed with ACS (recommended), or is pure-Graph /
   Direct-Routing a hard requirement (changes the whole design)?
2. **Outbound-only MVP first**, or inbound from day one?
3. **Call target** — primarily Teams users, Teams meetings, or PSTN via Teams?
   (Drives ACS identity setup.)
4. **Azure availability** — is there an Azure subscription + ACS resource + AAD
   app, or can they be created? Without these there is nothing to call.
5. **Encrypt the Teams client secret** in `TelephonyConfigurationModel`
   (deviating from the plaintext-creds norm)?

## Implications

- Adds a hard dependency on Azure (ACS billing + AAD) for any Teams calling.
- Introduces the first encrypted-at-rest telephony credential if Open-question 5
  is accepted (today telephony creds are plaintext JSONB; IM Channels use
  Fernet — a precedent exists in `api/services/im/encryption.py`).
- Reuses the existing pipecat WebSocket transport path and `TelephonyProvider`
  registry — no changes to the core call/audio plumbing, only a new provider
  package + serializer + an AAD token layer.
- "Teams" is delivered via ACS interop, not raw Graph; stakeholders expecting
  native Graph application-hosted media should note the Python constraint above.

## Related

- ADR-101 — Audio bridge (Asterisk ARI / AudioSocket path referenced by Option ②)
- `api/services/telephony/providers/telnyx/` — the template this provider mirrors
- `api/services/telephony/base.py`, `registry.py`, `factory.py` — extension points
