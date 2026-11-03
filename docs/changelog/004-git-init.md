# 004 — Git init and branch

## Context
OneMoreTime MVP B starts in `/Users/olegberdov/OneMoreTime` against remote `BerdovOleg/Y.Disk.Player`. Origin `main` held a legacy C# WebAppYDisk stub.

## Decision
Initialize local git (already done), track `origin`, create `feat/mvp-b` from `origin/main`, remove the legacy C# project, add `.gitignore` and a README stub. Prefer feature branch + PR over direct push to `main`.

## Changes
- `git init`, remote `origin` → `https://github.com/BerdovOleg/Y.Disk.Player.git`
- Branch `feat/mvp-b` from `origin/main`
- Removed `WebAppYDisk/` and `WebAppYDisk.sln`
- Added `.gitignore`, `README.md`, `docs/mvp-plan.md` stub

## Worked
Local repo connected; remote fetched; branch created.

## Failed / blocked
GitHub MCP declined by user; `gh` CLI not installed on PATH — PR will use `git push` and manual/API open if needed.

## Next
FastAPI skeleton + SQLite schema + static UI shell (005).
