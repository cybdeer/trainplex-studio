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
| `bv9unotdw` | docker compose build (orig) — LATE COMPLETION | ✅ COMPLETED at 16:06 IST (exit 0). Image tagged `trainplex-studio:dev` (1.53 GB). Was not actually stuck — silent poetry install just took ~28 min. Build watchdog 5-min idle threshold flagged it incorrectly. Container swap deferred to Week 3 branding step per founder. |

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

### 2026-05-15 — Day 1 Evening (Phase 1 Week 2 kick-off)

**Step 1.4-A: RBAC role field on User model + `@require_role()` decorator.**

#### Files Created

| File | Purpose |
|------|---------|
| `label_studio/users/migrations/0012_add_role_field.py` | Django migration — `AddField user.role` (CharField, 4 choices, default `trainer`) |
| `label_studio/users/decorators/__init__.py` | Package init — exports `require_role` |
| `label_studio/users/decorators/require_role.py` | DRF RBAC decorator — raises `PermissionDenied` for unauthenticated or out-of-role users |
| `label_studio/users/tests/test_role_rbac.py` | 7 unit tests covering model field + decorator behavior |

#### Files Modified

| File | Change |
|------|--------|
| `label_studio/users/models.py` | Added `ROLE_CHOICES` + `role = CharField(max_length=20, choices=ROLE_CHOICES, default='trainer')` on `User` |

#### Migration Applied

- `users.0012_add_role_field` → `OK` on dev DB (`/label-studio/data/label_studio.sqlite3`)
- Verified: `User.objects.first().role == 'trainer'` (default backfilled on existing row)

#### Tests

- Command: `docker exec -w /label-studio/label_studio trainplex-studio-dev /label-studio/.venv/bin/python -m pytest users/tests/test_role_rbac.py -v`
- Result: **7 passed in 23.08s** — covers default role, all 4 valid values, invalid-role rejection, admin allowed, qa_lead in multi-role set, trainer denied, anonymous denied.

#### Issues + Resolutions

| Issue | Resolution |
|-------|------------|
| `ceo@cybdeer.com` user does not exist in dev DB → `update(role='admin')` matched 0 rows | Logged; existing superuser is `vk.vinodparihar1@gmail.com` (founder). Admin user will be created when Step 1.4-B onboarding flow lands. |
| Local code not bind-mounted into pre-built dev container | `docker cp` round-trip — copy modified files into container before `makemigrations` / `pytest`, copy generated migration back out |
| `pytest` not in venv (pre-built image is runtime-only) | `pip install pytest pytest-django pytest-env factory-boy` inside venv |
| Bash on Windows mangles `/label-studio/...` paths in `docker exec -w` | Used PowerShell to invoke `docker exec` with absolute container paths |

#### 3-line Hindi recap (founder)

- Kya bug tha: User model mein role field nahi tha — sab user same level access.
- Usse kya ho rha tha: RBAC enforce nahi kar pa rahe the; admin/qa_lead/reviewer/trainer ka koi distinction nahi tha.
- Ab fix ke baad kya hoga: Har user ka ek role hoga (default `trainer`), aur `@require_role(['admin'])` lagao toh sirf admin hi wo API hit kar payega; baaki ko 403 milega.

---

### Step 15 — i18n bootstrap (Step 1.4-C)

**react-i18next infrastructure for Hindi/English UI strings.** Foundation only — no existing strings replaced yet. Phase 1 Week 2 Step 1.4-C delivered.

#### Files Created

| File | Purpose |
|------|---------|
| `web/libs/app-common/src/i18n/config.ts` | i18next init — registers `en` + `hi` resources, `LanguageDetector` (localStorage → cookie `tp_lang` → navigator), `fallbackLng: 'en'`, `defaultNS: 'common'`, `interpolation.escapeValue: false` |
| `web/libs/app-common/src/i18n/index.ts` | Barrel — re-exports `i18n`, `SUPPORTED_LANGUAGES`, `SupportedLanguage`, `useTranslation`, `Trans` |
| `web/libs/app-common/src/i18n/useTranslation.ts` | Thin re-export of `useTranslation` and `Trans` from `react-i18next` so app code imports from `@humansignal/app-common` only |
| `web/libs/app-common/src/i18n/__tests__/config.test.ts` | Unit tests — init, resource registration, `t('app.name')` EN, `t('trainer.dashboard_title')` HI, `{{tier}}` interpolation in HI |
| `web/libs/app-common/src/locales/en/common.json` | English baseline — `app`, `auth`, `common`, `trainer`, `admin` namespaces (37 keys total) |
| `web/libs/app-common/src/locales/hi/common.json` | Hindi (Devanagari) translation — exact same key shape as `en/common.json` |
| `web/libs/ui/src/components/HindiToggle/HindiToggle.tsx` | Small `<button>` that flips `i18n.language` between `en` and `hi`. Label shows the *target* language (`हि` when EN, `EN` when HI). `aria-label` always describes the switch action. |
| `web/libs/ui/src/components/HindiToggle/index.ts` | Named + default re-export for ergonomic imports |

#### Files Modified

| File | Change |
|------|--------|
| `web/libs/app-common/package.json` | Added `i18next ^23.15.1`, `react-i18next ^15.0.2`, `i18next-browser-languagedetector ^8.0.0` to `dependencies` (no `yarn install` run yet — will resolve on next workspace install) |
| `web/libs/app-common/src/index.ts` | Re-exports `i18n`, `SUPPORTED_LANGUAGES`, `useTranslation`, `Trans` + `SupportedLanguage` type from the new `./i18n` module |
| `web/libs/ui/src/index.ts` | Added `export * from "./components/HindiToggle"` so `@humansignal/ui` consumers can `import { HindiToggle } from "@humansignal/ui"` |

#### Tests

- Command: `nx run app-common:test` (jest, uses `web/libs/app-common/jest.config.ts`)
- **Status: deferred — not executed in this session.** Pre-built dev container is runtime-only; `web/node_modules` is not populated and `yarn install` was explicitly out of scope for this task (see task brief). The test file is wired correctly against `jest.config.ts` (no `moduleNameMapper` change needed — i18next is a normal CJS dep) and `tsconfig.spec.json` already includes `src/**/*.test.ts`. Run on next dev-loop iteration once workspace `yarn install` completes.

#### How to Use in Any Component

```tsx
import { useTranslation } from "@humansignal/app-common";

export function Greeting() {
  const { t } = useTranslation();
  return <h1>{t("app.name")}</h1>;        // → "TrainPlex Studio"
}
```

For interpolation:

```tsx
const { t } = useTranslation();
t("trainer.task_locked_tier", { tier: "silver" });
// EN → "Locked — promote to silver to unlock"
// HI → "बंद — silver में जाने पर खुलेगा"
```

For language switching anywhere in the app:

```tsx
import { HindiToggle } from "@humansignal/ui";

<HindiToggle />   // drop it into the header
```

Or programmatically:

```ts
import { i18n } from "@humansignal/app-common";
i18n.changeLanguage("hi");   // persists to localStorage `tp_lang` + cookie `tp_lang`
```

#### Detection Order

`localStorage('tp_lang')` → `cookie('tp_lang')` → `navigator.language` → fallback `en`.
Both cookie and localStorage caches are updated on every `changeLanguage` so the choice survives reloads + cross-subdomain navigation.

#### Issues + Resolutions

| Issue | Resolution |
|-------|------------|
| Task spec said `web/libs/ui/src/components/HindiToggle/` but existing UI lib convention is `web/libs/ui/src/lib/<Component>/` | Followed the explicit task path (`components/`) and added barrel re-export to `web/libs/ui/src/index.ts` so consumers don't care where it lives. Existing `lib/` components untouched. |
| `app-common/package.json` had empty `dependencies: {}` block | Replaced with the three i18next deps, keeping the same key ordering style as root `web/package.json` |
| No `yarn install` allowed in this env → cannot execute jest | Files staged correctly; test will run as part of normal CI / next manual `nx run app-common:test` once deps install. Imports + jest config verified by inspection. |

#### 3-line Hindi recap (founder)

- Kya bug tha: Hindi support ke liye koi framework nahi tha — har UI string hard-code English mein thi.
- Usse kya ho rha tha: India ke users (jo Hindi prefer karte hain) ke liye app fully samajhne yogya nahi tha; A/B test bhi nahi kar sakte the.
- Ab fix ke baad kya hoga: Naye components mein `const { t } = useTranslation(); <h1>{t('app.name')}</h1>` likhne se UI EN/HI dono mein dikhega. Header mein `<HindiToggle />` lagao toh user khud switch kar sakta hai. Choice browser mein save ho jayegi (`tp_lang` localStorage + cookie). Week 3 mein purani strings ek-ek karke `t()` se replace honge.

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
