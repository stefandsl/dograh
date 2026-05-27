/goal Mergiare il bot Telegram di stefandsl/CliClaw dentro stefandsl/dograh
come canale IM di prima classe, dockerizzato, gestibile dalla UI Dograh,
con installer one-liner che offre Telegram come opzione, e raggiungere
parità funzionale Syntx.ai-style (menu inline, voice dialog, sessions,
multi-tool routing). Risultato finale: tutto in main, documentato,
testato end-to-end, branch di lavoro chiusi, repo pulito.

================================================================
META-RULES (validi per TUTTI i sub-goal)
================================================================
- NON fare domande di chiarimento all'utente per scelte di
  implementazione. Se hai dubbi, ricavi la risposta da: (1) codice
  esistente, (2) docs ufficiali Dograh (docs.dograh.com), (3) docs
  aiogram 3.x, (4) docs Telegram Bot API, (5) docker-compose del repo.
  In ultima istanza scegli l'opzione meno invasiva e DOCUMENTI la
  scelta in docs/adr/.
- ECCEZIONE: chiedere SEMPRE prima di azioni distruttive
  (archive repo altrui, force-push, modifiche all'installer pubblico
  che rompono utenti esistenti).
- Usa sub-agenti via Task tool con istruzioni autocontenute quando ha
  senso (research, scan codebase ampio). Non delegare la sintesi.
- Branch strategy: feature/merge-cliclaw-phase-N (uno per fase).
- Commit convention: Conventional Commits.
- Ogni fase termina con: tests green + healthcheck OK + PR opened/merged.
- Telemetria: ENABLE_TELEMETRY=false in tutti gli ambienti di test.
- Secrets: mai committare token. Usa .env.example + entry in .env (gitignored).

================================================================
SEQUENZA FASI
================================================================
PHASE 0 — RESEARCH & MAPPING (no code yet)
PHASE 1 — SCAFFOLDING REPO (telegram-bot/ dir + compose service)
PHASE 2 — PORT CLICLAW CORE (drop CLI backends, wire Dograh API)
PHASE 3 — VOICE BRIDGE INBOUND (Path A aiortc o Path B web link)
PHASE 4 — UI DOGRAH "IM CHANNELS" (Next.js route + FastAPI router)
PHASE 5 — SYNTX-STYLE MENU & FUNZIONALITÀ (9 pulsanti cablati)
PHASE 6 — INSTALLER ONE-LINER CON OPZIONE TELEGRAM
PHASE 7 — DOCS & ADR
PHASE 8 — INTEGRATION TEST END-TO-END (CI)
PHASE 9 — MERGE, RELEASE, CLEANUP (richiede consenso esplicito su archive CliClaw)

================================================================
DONE WHEN
================================================================
1. Da una VM Debian fresh, il curl one-liner produce: UI Dograh, bot
   Telegram online che risponde a /start con menu funzionante.
2. Sezione "IM Channels" nella UI Dograh permette di gestire token
   senza ridistribuire il bot.
3. Voice call end-to-end Telegram ↔ Dograh WebCall funziona < 5s round-trip.
4. Repo dograh main is green (CI + e2e).
5. CHANGELOG + release tag + docs completi.
6. Repo CliClaw archived (richiede conferma esplicita).
