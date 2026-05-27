# PHASE 7 — User-facing docs

**Branch:** `feat/merge-cliclaw-phase-7`

## Files
- `docs/channels/telegram.md` — full setup walkthrough (create bot via @BotFather, plug token into UI, troubleshoot common issues)
- `docs/channels/architecture.md` — mermaid diagram of the path Telegram ↔ bot container ↔ Dograh API ↔ WebRTC ↔ TURN
- `README.md` (root):
  - new section under Features: "📨 IM Channels (Telegram, more soon)"
  - replace the curl-pipe install command with the new `install.sh` one-liner
  - link to `docs/channels/telegram.md`
- `CHANGELOG.md` — entry "feat: Telegram channel integration (CliClaw merge)"
- `docs/adr/ADR-*.md` — already created in Phase 0; keep consistent

## Out of scope
- Italian translation. Skip unless explicitly asked.
- Updating `docs.dograh.com` if it's a separate repo. Note in the PR description but don't open cross-repo PRs without consent.

## Verifier
- `markdownlint` clean.
- mermaid diagrams render (test via `mmdc` if installed).
- `markdown-link-check` on the changed files — no broken internal links.
