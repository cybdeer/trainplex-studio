# TrainPlex Studio — Build Log

Founder रिकॉर्ड के लिए हर step + decision यहाँ। हर stage पर update होता है।

---

## 2026-05-15 — Day 1 (Phase 1 Week 1)

### Decisions

| # | Decision | Reason |
|---|----------|--------|
| 1 | Fork repo `cybdeer/trainplex-studio` from `HumanSignal/label-studio` (Apache 2.0) | Zero license cost, full customization possible |
| 2 | Public visibility (not Private) | GitHub fork can't be made private; Apache 2.0 anyway open-source; secrets stay in env/Secrets |
| 3 | 2FA enabled on GitHub account | Security baseline (Step 12), pre-June 2026 deadline |
| 4 | Default branch `develop` (not `main`) | LS upstream convention; main reserved for stable tags |
| 5 | gh CLI used for clone (not raw https) | Bypasses 2FA prompt; uses stored OAuth token |
| 6 | Pre-built `heartexlabs/label-studio:latest` image used for dev | `docker compose build` got stuck twice on poetry install step (silent network slowness). Pre-built skips 30 min build for now. Will rebuild when actual customizations applied (Week 2-3 onward). |
| 7 | Dev container on port `:8090` (not `:8080`) | Avoids conflict with TrainPlex production stack on `:8080` |
| 8 | Founder + Claude do everything; no external dev | `₹0` cost model per plan |

### Files Created

| File | Purpose | Step |
|------|---------|------|
| `docs/ARCHITECTURE_MAP.md` | Backend + frontend file map for 7 customization priorities | 1.3 |
| `docs/CICD_SETUP.md` | CI/CD secrets + branch protection runbook | 10 |
| `docs/BUILD_LOG.md` | This file — full build record | — |
| `.github/workflows/test.yml` | PR/push test job (lint + unit + integration + Docker build) | 10.1 |
| `.github/workflows/deploy-staging.yml` | Develop branch → staging auto-deploy | 10.1 |
| `.github/workflows/deploy-prod.yml` | Main branch → prod with manual approval + auto-rollback | 10.1 |
| `.github/dependabot.yml` | Weekly pip + npm + actions vuln scan | 10, 12 |
| `.github/CODEOWNERS` | Solo dev (@ilo265) | 10 |
| `.github/pull_request_template.md` | PR checklist with plan reference | 10 |
| `web/libs/ui/src/tokens/tokens.trainplex.css` | TrainPlex brand color/typography/spacing tokens | 5.1 |

### Files Modified

| File | Change |
|------|--------|
| `.github/CODEOWNERS` | Replaced upstream HumanSignal owners with @ilo265 |
| `.github/dependabot.yml` | Replaced upstream config with TrainPlex weekly Monday schedule |
| `.github/pull_request_template.md` | Replaced upstream comment-only with checklist template |

### Git Commits

| SHA | Message | Files | Date |
|-----|---------|-------|------|
| `9e67f71` | feat(trainplex): Phase 1 Week 1 — fork scaffolding | 9 files, +1317 -32 | 2026-05-15 15:38 IST |

Pushed to `origin/develop` (cybdeer/trainplex-studio).

### Local Setup

| Resource | Value |
|----------|-------|
| Clone path | `C:\TrainPlex\trainplex-studio` |
| Files extracted | 5208 |
| Commits in history | 6391 |
| Python (host) | 3.12.10 |
| Node (host) | v25.9.0 |
| Docker (host) | 29.4.3 |
| Git (host) | 2.53.0 |
| gh CLI | 2.90.0 (logged in as `ilo265`) |

### Dev Environment

| Component | Status | URL / Detail |
|-----------|--------|--------------|
| LS dev container | ✅ Running | `trainplex-studio-dev` (heartexlabs/label-studio:latest) |
| Port mapping | ✅ Working | `:8090` (host) → `:8080` (container) |
| Data volume | ✅ Mounted | `C:\TrainPlex\trainplex-studio\mydata` → `/label-studio/data` |
| Database | ✅ SQLite | Inside container `/label-studio/data/label_studio.sqlite3` |
| Server | ✅ WSGIServer | Python 3.13.12 |

### Dev Admin Account (DO NOT use in production)

| Field | Value |
|-------|-------|
| Email | `vk.vinodparihar1@gmail.com` |
| Password | `TrainPlexDev2026!` |
| User ID | 2 |
| Name | Vinod Parihar |
| Is superuser | True |
| Is staff | True |
| Organization | TrainPlex Dev (id=1, owner: vk.vinodparihar1@gmail.com) |

**History:**
- 15:50 IST — `ceo@cybdeer.com` (id=1) created as initial admin (tester account, mistake)
- 16:25 IST — Founder corrected: real admin = `vk.vinodparihar1@gmail.com`. Created Vinod (id=2), transferred org ownership, deleted ceo (id=1). Total users now: 1 (Vinod only).
- Verified: Vinod login HTTP 302 + projects page HTTP 200. Old ceo login redirects to login (no auth) — confirmed deleted.

⚠️ **This password is for local dev container only.** Production will use unique strong passwords via Step 12 (Security Baseline). This file in `docs/` may be gitignored when production credentials get added.

### Verified Endpoints

| Endpoint | HTTP | Notes |
|----------|------|-------|
| `http://localhost:8090/` | 302 | Redirects to login (expected for unauthenticated) |
| `http://localhost:8090/user/login/` | 200 | Login form renders |
| `http://localhost:8090/health` | 200 | Health endpoint OK |
| `http://localhost:8090/static/icons/logo.svg` | 200 | Static assets served |
| Login POST + Projects page (authenticated) | 302 → 200 | Admin session working |

### Background Tasks Run

| ID | Task | Outcome |
|----|------|---------|
| `bmsy1zqfi` | git clone via HTTPS (no auth cached) | FAILED — stuck 15 min, killed |
| `aeedf0e56c3a30bd1` | Architecture map sub-agent (Explore) | FAILED — prompt too long (Claude internal) |
| `ade6f16179108132d` | Architecture map sub-agent retry shorter | FAILED — same error |
| `a896601433ecdc07b` | CI/CD workflows sub-agent | ✅ COMPLETED — 7 files |
| `bv9unotdw` | docker compose build (first try) | STUCK on poetry install step #36 |
| `bftod8mri` | docker compose build (verbose retry) | STUCK same step; stopped |
| `boy6376rv` | Build watchdog monitor | STOPPED when build skipped |
| `bggm1iwak` | LS health-check until-loop | ✅ COMPLETED — LS up in ~40s |

### Issues + Resolutions

| Issue | Resolution |
|-------|------------|
| `git clone` HTTPS stuck 15 min, 0 KB downloaded | Used `gh repo clone` (OAuth token) — succeeded |
| GitHub Fork visibility can't be Private | Decided: keep public (Apache 2.0 already public, no secrets in code) |
| Sub-agent "Prompt too long" twice | Did architecture mapping manually via Glob/Grep/Read |
| Docker build stuck on poetry install (no errors, no progress) | Skipped build; pulled pre-built `heartexlabs/label-studio:latest` from Docker Hub |
| Port 8080 conflict with production stack | Used 8090 for dev |
| Bash `python /label-studio/...` MSYS path mangled | Used PowerShell here-string + `docker exec -i` |

### Watchdog Pattern Established

- Background tasks use `run_in_background: true`
- Long-running monitored via `Monitor` tool with stuck detection (5 min idle threshold)
- Heartbeat every 2 min for visibility
- Auto-kill on stuck; fallback path (e.g. pre-built image) tried instead

### Phase 1 Week 1 Status

| Step | Status |
|------|--------|
| 1.1 Fork repo | ✅ Done |
| 1.2 Local dev setup | ✅ Done (via pre-built image fallback) |
| 1.3 Architecture study | ✅ Done — `docs/ARCHITECTURE_MAP.md` |
| 5.1 Design tokens (foundation) | ✅ Done — `tokens.trainplex.css` |
| 10 CI/CD scaffolding | ✅ Done — workflows + dependabot + PR template |
| 12 Security baseline (2FA + Dependabot) | ⏳ Partial (2FA done; rate-limit / headers Week 2) |

### Week 2 Kickoff Plan

- **Step 1.4-A:** RBAC role field migration on `users.User`
- **Step 1.4-C:** i18n framework bootstrap (`web/libs/app-common/src/i18n/`)
- **Step 2.1:** Template gallery — load 50 native LS templates + start 10 India-custom
- **Step 9.1:** pytest framework setup (backend test infra)

---

## Log Update Rules

- Every new file → `Files Created` table
- Every modified existing file → `Files Modified` table
- Every git commit → `Git Commits` table
- Every issue + fix → `Issues + Resolutions` table
- Every new admin / user / project → recorded with timestamp
- Every container start / stop / restart → recorded
- New section per day (## YYYY-MM-DD — Day N)

Founder can read this anytime to see what was built + what decisions taken.
