# PHASE 9 — Release + cleanup + (optional) archive CliClaw

**Branch:** none new — works on `main` after all phase PRs are merged.

## Steps

1. Verify all `feature/merge-cliclaw-phase-*` PRs are merged.
2. Bump version (release-please if configured, otherwise manual SemVer minor bump).
3. `gh release create vNEXT --generate-notes` with custom highlights for Telegram channel.
4. Prune merged remote branches:
   ```bash
   for b in $(gh pr list --state merged --json headRefName \
     -q '.[].headRefName' | grep '^feature/merge-cliclaw'); do
     gh api -X DELETE "repos/stefandsl/dograh/git/refs/heads/$b" || true
   done
   ```
5. Local cleanup: `git remote prune origin && git gc --aggressive`.
6. Close any auto-opened issues referenced by the merged PRs.

## ⚠️ DESTRUCTIVE — needs explicit "yes archive CliClaw"

If and only if the user explicitly says "archive CliClaw":

```bash
# 1. README banner on top
gh repo clone stefandsl/CliClaw /tmp/cliclaw-archive
cd /tmp/cliclaw-archive
# prepend banner to README
git add README.md && git commit -m "docs: merged into dograh, archiving"
git push

# 2. Archive flag
gh api -X PATCH repos/stefandsl/CliClaw -f archived=true
```

Without consent: skip the archive step; leave CliClaw alone.

## Done when
- `gh release view vNEXT` exists
- main green
- no `feature/merge-cliclaw-*` branches on the remote
- README points at the new `install.sh`
- Fresh VM + curl one-liner → working Dograh + Telegram bot
