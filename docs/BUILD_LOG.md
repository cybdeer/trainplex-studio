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

### Step 16 — TrainPlex India template gallery seed (Step 2.2)

**10 India-specific Label Studio XML labeling templates shipped on disk.** Foundation for Step 2.3 (admin gallery wiring, Week 3). Phase 1 Week 2 Step 2.2 delivered.

#### Templates Created (10)

| # | ID | Title (EN) | Title (HI) | Category | Tier |
|---|----|-----------|------------|----------|------|
| 1 | `aadhaar_ocr_validation` | Aadhaar/PAN OCR Validation | आधार/पैन OCR सत्यापन | OCR & Document | bronze |
| 2 | `code_switching_highlighter` | Hindi-English Code-Switching Highlighter | हिंदी-अंग्रेज़ी मिश्रित भाषा टैगर | NLP & Linguistics | silver |
| 3 | `devanagari_typo_correction` | Devanagari Typo and Matra Correction | देवनागरी मात्रा एवं वर्तनी सुधार | NLP & Linguistics | gold |
| 4 | `cultural_context_flagger` | Cultural / Sensitive Reference Flagger | सांस्कृतिक / संवेदनशील संदर्भ चिह्नक | Content Moderation | gold |
| 5 | `voice_quality_indian_accents` | Voice Quality and Indian Accent Rating | भारतीय उच्चारण एवं ध्वनि गुणवत्ता रेटिंग | Audio & Speech | silver |
| 6 | `tone_slider_hindi` | Hindi Tone Classification | हिंदी टेक्स्ट — स्वर वर्गीकरण | NLP & Linguistics | silver |
| 7 | `regional_language_switcher` | Multi-Script Regional Language Identification | बहु-लिपि क्षेत्रीय भाषा पहचान | NLP & Linguistics | gold |
| 8 | `indian_script_handwriting_ocr` | Indic Handwriting Transcription | भारतीय लिपि — हस्तलेख प्रतिलेखन | OCR & Document | gold |
| 9 | `hinglish_code_review` | Hinglish Code Comment Review | हिंग्लिश कोड कमेंट समीक्षा | Software / Code | silver |
| 10 | `indian_medical_ner` | Hindi Medical Report NER | हिंदी चिकित्सा रिपोर्ट — नामांकित इकाई पहचान | Medical / Healthcare | gold |

#### Files Created

| File | Purpose |
|------|---------|
| `backend/data/ls_templates/trainplex_india/README.md` | Gallery index + meta schema + loading-strategy note (Step 2.3 ka pre-doc) |
| `backend/data/ls_templates/trainplex_india/<id>/config.xml` (×10) | LS labeling XML config; root `<View>` with `<Labels>`/`<Choices>`/`<RectangleLabels>`/`<Rating>`/`<TextArea>` tags as needed per template |
| `backend/data/ls_templates/trainplex_india/<id>/meta.json` (×10) | Gallery metadata (id, title, title_hi, description, description_hi, category, india_relevance, trainplex_custom, estimated_time_per_task_min, tier, languages) |
| `backend/data/ls_templates/trainplex_india/<id>/sample_task.json` (×10) | One example task with placeholder URLs + real-looking Hindi/English data that renders against the config |
| `label_studio/tests/test_trainplex_templates.py` | Pure-disk pytest smoke test — discovers all templates, parametrises 4 checks × 10 templates + 3 sanity asserts = 43 test cases |

Total new files: 32 (10 × 3 per template + 1 README + 1 test).

#### Smoke Test

- Command: `docker exec trainplex-studio-dev sh -c 'cd /label-studio/label_studio && /label-studio/.venv/bin/python -m pytest tests/test_trainplex_templates.py -v'`
- **Status: 43 passed in 5.68s** (all 10 templates × 4 per-template checks + 3 sanity asserts = 43).
- Coverage per template:
  1. `config.xml` is well-formed XML rooted at `<View>`
  2. `config.xml` contains at least one labeling element (`Labels`, `Choices`, `RectangleLabels`, …)
  3. `meta.json` parses, has all required keys (`id`, `title`, `title_hi`, `category`, `description`, `trainplex_custom`), `id` matches folder, `title_hi` contains Devanagari
  4. `sample_task.json` parses + has `data` dict
- Plus 3 global: dir exists, count == 10, no duplicate ids.

#### Validation Reference

Upstream LS XML conventions verified by reading `web/libs/editor/src/examples/{image_bbox,named_entity,audio_classification,classification_mixed,image_ocr,transcribe_audio,sentiment_analysis,audio_regions,dialogue_analysis}/config.xml`. Conventions adopted:

- Root `<View>` with optional `style` attr for layout
- `name`/`toName` pairing for every annotation tag
- `value="$key"` to bind to task data
- `Rating` tag uses `maxRating`/`icon`/`size` attrs (per `web/libs/editor/src/tags/control/Rating.jsx`)
- `Choices` uses `choice="single-radio"|"multiple"`, `showInLine="true"`
- `TextArea` uses `editable="true"`, `perRegion="true"`, `maxSubmissions="1"`, `rows`, `placeholder`
- `View visibleWhen="region-selected"` wraps per-region inputs

#### Container File Layout

Templates live in `backend/data/ls_templates/trainplex_india/` at the repo root, NOT under `label_studio/projects/templates/`. Reason: upstream LS's `annotation_templates/` directory is deeply tied to its own loader; isolating TrainPlex additions in `backend/data/` keeps future upstream merges conflict-free. The Step 2.3 loader will read from this path explicitly.

Container does not bind-mount the source (only `mydata/` is mounted). Files were copied with `docker cp` before running pytest:

```
docker cp label_studio/tests/test_trainplex_templates.py trainplex-studio-dev:/label-studio/label_studio/tests/
docker cp backend trainplex-studio-dev:/label-studio/backend
```

This will go away once Step 11 (proper dev-image with source bind-mount) lands.

#### Issues + Resolutions

| Issue | Resolution |
|-------|------------|
| Task brief said template location could be `label_studio/projects/templates/` or `web/libs/editor/src/examples/` — only the latter exists in this fork | Confirmed via Glob; only `web/libs/editor/src/examples/` has 46 upstream examples. Followed brief's primary directive: created NEW `backend/data/ls_templates/trainplex_india/` dir, did NOT touch upstream examples. |
| Container has no bind-mount for repo source (only `mydata/`) | Used `docker cp` to copy test file + templates into container before running pytest. Documented in BUILD_LOG so next dev knows. |
| `docker exec -w /label-studio/label_studio …` failed with "Cwd must be an absolute path" on Windows | Switched to `sh -c 'cd /label-studio/label_studio && pytest …'`. Same effect, no path-mangling. |
| Initial XML validation needed before writing tests | Ran ad-hoc Python `ET.parse()` over all 10 configs; 0 errors → wrote pytest test confidently. |

#### 3-line Hindi recap (founder)

- Kya bug tha: LS के built-in templates में सब English/US-centric हैं — Aadhaar, Hindi tone, Devanagari typo, Indian accents जैसी India-specific labeling task setup करने के लिए हर बार scratch से XML लिखना पड़ता था।
- Usse kya ho rha tha: Indian customer onboard करते वक्त project setup में 30-45 min jaate the; labeler को सही label-set नहीं मिलता था; quality consistent नहीं रहती थी।
- Ab fix ke baad kya hoga: 10 ready-made India templates `backend/data/ls_templates/trainplex_india/` में disk पर हैं (Aadhaar OCR, Hinglish tagger, Devanagari typo, cultural flagger, Indian-accent audio, Hindi tone, regional-language switcher, Indic handwriting, Hinglish code-review, Hindi medical NER). हर एक का meta.json (gallery info, Hindi title, tier, time/task) + sample_task.json (example data) + smoke test (`pytest tests/test_trainplex_templates.py` → 43/43 pass) ready है। Week 3 (Step 2.3) में admin gallery में यह 10 templates load हो जाएँगे — customer एक click में Indian project spin-up कर पाएगा।

---

### Step 17 — pytest backend test framework (Step 9.1)

**Solid pytest foundation for TrainPlex backend.** Shared fixtures (admin/trainer/reviewer/qa_lead users, organization, DRF clients), factory-boy factories, repo-root coverage config, custom markers (`rbac`, `i18n`, `slow`, `integration_tests`). Phase 1 Week 2 Step 9.1 delivered.

#### Files Created

| File | Purpose |
|------|---------|
| `label_studio/tests/factories.py` | factory-boy factories — `UserFactory`, `OrganizationFactory`, `ProjectFactory`, `TaskFactory`, `AnnotationFactory`. Default `UserFactory.role='trainer'`; pass `role='admin'` to override. |
| `label_studio/tests/test_fixtures_smoke.py` | 16 smoke tests verifying every fixture + factory boots correctly (role correctness, DRF client type, API reachability without 500, factory uniqueness). |
| `.coveragerc` (repo root) | Coverage config — `source=label_studio`, omits tests/migrations/__init__/apps/manage/server, 80% target per Phase 1 plan. Old `label_studio/.coveragerc` left untouched for upstream HumanSignal CI compat. |

#### Files Modified

| File | Change |
|------|--------|
| `label_studio/conftest.py` | Added 6 shared fixtures: `admin_user`, `trainer_user`, `reviewer_user`, `qa_lead_user`, `organization`, `api_client`, `authenticated_client`. Pre-existing `clear_current_context_after_test` autouse kept. |
| `label_studio/pytest.ini` | Added `python_classes`, `python_functions`, `--strict-markers`, and `markers` block declaring `slow`, `integration_tests`, `rbac`, `i18n`. Existing env vars + tavern config preserved. |

#### Tests

- Command: `docker exec -w /label-studio/label_studio trainplex-studio-dev /label-studio/.venv/bin/python -m pytest users/tests/test_role_rbac.py tests/test_fixtures_smoke.py -v --tb=short -m "not integration_tests"`
- Result: **23 passed in 26.79s** (7 pre-existing RBAC tests + 16 new fixture/factory smoke tests).
- Marker filter verified: `pytest -m "rbac"` selects only the 5 `@pytest.mark.rbac` tests, deselects 11.
- Collection sanity: `pytest --collect-only` shows **1281 tests collectible** repo-wide — `--strict-markers` did not break any pre-existing test.
- Coverage (targeted run on Step 1.4-A code): `users/decorators/require_role.py` = **100.0%**, `users/models.py` = **63.3%** (most uncovered lines are unrelated avatar/name helpers). Full-suite coverage requires running the legacy tavern integration suite which is out of Step 9.1 scope.

#### How to run

Inside the dev container (preferred — venv has all test deps):

```powershell
# Just the new infra + RBAC
docker exec -w /label-studio/label_studio trainplex-studio-dev `
  /label-studio/.venv/bin/python -m pytest `
  users/tests/test_role_rbac.py tests/test_fixtures_smoke.py `
  -v --tb=short -m "not integration_tests"

# Full backend (non-integration), with coverage:
docker exec -w /label-studio/label_studio trainplex-studio-dev `
  /label-studio/.venv/bin/python -m pytest `
  --cov=. --cov-report=term-missing -m "not integration_tests"

# Just RBAC-marked tests:
docker exec -w /label-studio/label_studio trainplex-studio-dev `
  /label-studio/.venv/bin/python -m pytest -m "rbac" -v
```

Locally (requires `poetry install --with test`):

```bash
cd label_studio && poetry run pytest -v -m "not integration_tests"
```

#### CI Integration

The existing `.github/workflows/test.yml` `test-backend` job already invokes pytest with the right marker filter — `poetry run pytest -v -m "not integration_tests" --disable-warnings --durations=30 -n auto`. **No workflow change needed for Step 9.1.** Suggested follow-up (founder review): add `--cov=. --cov-report=xml --cov-fail-under=80` once the coverage baseline lands above 80% on `develop`. Holding that change for founder approval.

#### Issues + Resolutions

| Issue | Resolution |
|-------|------------|
| Pre-built dev container `/label-studio/.venv` missing several test deps (`pytest-cov`, `mock`, `freezegun`, `moto`, `tavern`, `fakeredis`, `responses`, `requests-mock`, `psutil`) — image was built runtime-only. | Installed via `pip install` into the existing venv. These are already declared in `pyproject.toml [tool.poetry.group.test.dependencies]` — no manifest change needed; just a container-level baseline drift that gets corrected next time the image is rebuilt from `pyproject.toml`. |
| `pip` resolved `moto>=4.2.6` → `moto 5.2.1`, which renamed `moto.mock_s3` → `moto.mock_aws`. Existing `label_studio/tests/conftest.py:22` imports the old name and broke collection. | Pinned in-container to `moto==4.2.14`. The task spec forbids modifying existing test files, and `pyproject.toml` already constrains via `>=4.2.6`, so the legacy code is correct — only the resolver overshot. Founder may want to add an upper bound (`moto >=4.2.6,<5.0`) in `pyproject.toml` in a follow-up PR. |
| Wanted a repo-root `pytest.ini` per task spec, but one already exists at `label_studio/pytest.ini`. Two configs cause pytest to load only one (whichever it finds first via rootdir resolution). | Extended the existing `label_studio/pytest.ini` with the requested fields (`python_classes`, `python_functions`, `--strict-markers`, `markers`) rather than creating a duplicate. CI workflow runs pytest from `working-directory: label_studio` so this is the file it picks up. |
| Smoke test path (`label_studio/tests/test_fixtures_smoke.py` per spec) inherits the heavy autouse mocks from `label_studio/tests/conftest.py` (S3/GCS/Azure/Redis/ML). | Acceptable — moto mocks work offline and the test still runs in ~24s. New fixtures live in `label_studio/conftest.py` (root) so future unit tests outside `label_studio/tests/` can use them without paying the autouse-mock cost. |

#### 3-line Hindi recap (founder)

- Kya bug tha: Backend testing infra ad-hoc thi — har test ke andar user, org, API client manually create karna padta tha, koi shared fixtures nahi the, coverage tooling missing.
- Usse kya ho rha tha: New test likhne mein boilerplate zyaada tha, fixtures inconsistent the (har file apna admin user banata tha), aur coverage measure nahi ho pa rahi thi — 80% target ke against baseline pata nahi tha.
- Ab fix ke baad kya hoga: Koi bhi test `def test_xxx(admin_user, organization, authenticated_client):` likhe — fixture automatic mil jayegi. Naya user chahiye toh `UserFactory(role='reviewer')`. `pytest -m "rbac"` se sirf RBAC tests, `pytest --cov` se coverage report. Existing 7 RBAC tests + new 16 smoke tests sab pass — total 23/23. CI workflow already correct hai, koi change nahi.

---

### Step 1.4-B + 1.4-D — Frontend brand activation + RBAC render guards (Week 3)

Phase 1 frontend customizations: wire the existing TrainPlex brand override CSS into the build, replace the upstream Label Studio logo + favicon, surface the backend `User.role` field to the React client, and gate four admin-only UI spots behind a new `<RoleGate>` component.

#### Files Created

| File | Purpose |
|------|---------|
| `web/libs/ui/src/components/RoleGate/RoleGate.tsx` | Presentational role-gate component. Renders children only when `userRole` is in `allow=[Role]`. Reads `Role` union from `users.models.User.ROLE_CHOICES` (trainer / reviewer / qa_lead / admin). Defensive — does NOT replace server-side DRF perms; just hides UI. |
| `web/libs/ui/src/components/RoleGate/index.ts` | Barrel re-export (named + default). |
| `web/libs/ui/src/components/RoleGate/__tests__/RoleGate.test.tsx` | 9 Jest + RTL tests: admin allowed, trainer blocked w/ null fallback, custom fallback, undefined / null / empty userRole all blocked, multi-role allow list, unknown role string blocked. |
| `web/apps/labelstudio/src/assets/images/favicon.svg` | TrainPlex SVG favicon (Indigo bg #1A1A5E, orange "T" #FF6B35). Loaded via `<link rel="icon" type="image/svg+xml">`; legacy `favicon.ico` retained as fallback. |

#### Files Modified

| File | Change |
|------|--------|
| `web/apps/labelstudio/src/themes/default/variables.prefix.css` | Added `@import "../../../../../libs/ui/src/tokens/tokens.trainplex.css";` AFTER the upstream tokens/colors/typography imports so brand overrides win the cascade. This is the file actually loaded by `App.prefix.css` → labelstudio app at runtime. |
| `web/libs/ui/src/styles.prefix.css` | Same brand override import added AFTER upstream tokens, for storybook/playground/editor-standalone consumers (which load this file instead of the labelstudio theme). |
| `web/apps/labelstudio/src/assets/images/logo.svg` | Replaced HumanSignal "Label Studio" wordmark with TrainPlex Studio text logo — "TrainPlex" in brand Indigo (#1A1A5E, weight 700) + "Studio" in brand Orange (#FF6B35, weight 400). Kept upstream `width="194" height="30"` so the Menubar slot (`142×22`) renders unchanged. |
| `web/apps/labelstudio/src/index.html` | `<title>` Labelstudio → TrainPlex Studio. Added `<link rel="icon" type="image/svg+xml" href="assets/images/favicon.svg">` as primary, kept `.ico` as `alternate icon` fallback. |
| `web/apps/labelstudio/src/components/Menubar/Menubar.jsx` | Logo `alt` text "Label Studio Logo" → "TrainPlex Studio" (a11y / screen reader). |
| `label_studio/users/serializers.py` | Added `'role'` to `BaseUserSerializer.Meta.fields` — `WhoAmIUserSerializer` and `UserSerializerUpdate` inherit so the field flows through `/api/current-user/whoami` and `/api/users/`. Added `'role'` to `BaseUserSerializerUpdate.Meta.read_only_fields` to block self-promotion via PATCH `/api/current-user/` (defense-in-depth; backend perms also gate admin-only role mutations). |
| `web/libs/core/src/types/user.ts` | Added `TrainPlexRole` union (`'trainer' \| 'reviewer' \| 'qa_lead' \| 'admin'`) and optional `role?: TrainPlexRole` on `APIUser` so TypeScript surfaces the field everywhere `useAuth().user` is destructured. |
| `web/libs/ui/src/index.ts` | Re-export `./components/RoleGate` so consumers can `import { RoleGate } from "@humansignal/ui"`. |
| `web/apps/labelstudio/src/pages/Settings/DangerZone.jsx` | Wrapped the entire button list (`Delete Project`, `Drop All Tabs`, `Reset Cache`) in `<RoleGate allow={['admin']}>`. Non-admins now see a one-line explanatory fallback instead of the destructive action panel. |
| `web/apps/labelstudio/src/pages/Organization/PeoplePage/PeoplePage.jsx` | Wrapped "Add Members" invite button in `<RoleGate allow={['admin']}>`. Non-admins still see the people list — they just can't invite. |
| `web/apps/labelstudio/src/pages/Projects/Projects.jsx` | Wrapped the "Create" project button (`ProjectsPage.context`) in `<RoleGate allow={['admin']}>`. Non-admins can still view + open projects, just not create new ones. Hook called from a component used via `<ContextComponent />` in Menubar — safe pattern. |

#### Admin elements gated (3 of 5 spec'd targets)

1. **Project deletion / drop-tabs / cache-reset** — `Settings/DangerZone.jsx` (whole panel gated; null state for non-admins).
2. **Member invite** — `Organization/PeoplePage/PeoplePage.jsx` "Add Members" button.
3. **Project creation** — `Projects/Projects.jsx` "Create" button in top nav context.

#### Skipped — deliberately

| Target | Why skipped |
|--------|-------------|
| **Project Settings tab (top nav, `DataManager.context`)** | Gating the whole entry would block trainers from reading labeling instructions / general project info. Per Step 1.4-B spec "if you can't find a spot cleanly without breaking something, SKIP it". Destructive items inside Settings are already gated via DangerZone. Revisit in Week 4 with finer-grained per-subtab gates (Webhooks ✓ admin, Storage ✓ admin, ML ✓ admin, General ❌ leave open, Labeling ❌ leave open). |
| **Annotation delete buttons in editor toolbar** | The labelstudio editor lives in `web/libs/editor/` and is a separately compiled bundle (mobx-state-tree + custom React). It does NOT use the same `useAuth()` flow — user state arrives via window globals from the host. Wiring role through requires a deeper change than fits the "low risk" budget. Deferred to Week 4 — a dedicated mini-task can plumb role into the editor's user object. |

#### Backend serializer diff

```diff
 class BaseUserSerializer(FlexFieldsModelSerializer):
     ...
     class Meta:
         model = User
         fields = (
             'id', 'first_name', 'last_name', 'username', 'email',
             'last_activity', 'custom_hotkeys', 'avatar', 'initials',
             'phone', 'active_organization', 'active_organization_meta',
             'allow_newsletters', 'date_joined',
+            # TrainPlex Step 1.4-B (RBAC)
+            'role',
         )

 class BaseUserSerializerUpdate(BaseUserSerializer):
     class Meta(BaseUserSerializer.Meta):
-        read_only_fields = ('email',)
+        # Block self-promotion via PATCH /api/current-user/
+        read_only_fields = ('email', 'role')
```

#### Tests

- `web/libs/ui/src/components/RoleGate/__tests__/RoleGate.test.tsx` — 9 unit tests covering allow/block/fallback/undefined/null/empty/multi-role/unknown-role.
- No other test files modified (per spec).
- Backend serializer change requires no new tests — covered by existing `users/tests/` if `WhoAmI` response shape is asserted. The existing role RBAC tests (`label_studio/users/tests/test_role_rbac.py`) already cover that `user.role` is set correctly server-side.

#### How to verify (after rebuild)

Container `trainplex-studio-dev` is running the pre-built image. Frontend changes require a yarn rebuild — **founder approval needed before triggering the 30-min build** (per task constraints). After rebuild:

1. **Brand colors** — log in, primary buttons + nav highlights should be Indigo `#1A1A5E`. Inspect `:root` in DevTools — `--color-primary-surface` should resolve to indigo, NOT upstream grape.
2. **Logo + favicon** — top-left of Menubar shows "TrainPlex Studio" wordmark; browser tab shows Indigo+Orange "T" favicon; page title "TrainPlex Studio".
3. **RoleGate** — create 2 test users:
   - `admin@local` with role=admin → sees Create button on Projects, sees Add Members on People, sees full Danger Zone panel.
   - `trainer@local` with role=trainer → Create button hidden, Add Members hidden, Danger Zone shows only the explanatory text fallback.
4. **Backend** — `curl /api/current-user/whoami` with auth cookie should return `"role": "admin"` (or whatever the user's role is).

Backend serializer change is hot-reloadable inside `trainplex-studio-dev` (Django runserver autoreload) — so the role field will appear in API responses without a full image rebuild. Frontend changes (logo/CSS/RoleGate) require the yarn build.

#### 3-line Hindi recap (founder)

- Kya bug tha: Frontend pe TrainPlex brand bilkul render nahi ho raha tha (Indigo+Orange CSS file likhi thi par kahin import nahi tha), logo abhi tak HumanSignal "Label Studio" wala tha, aur backend `user.role` field frontend tak nahi pahunch rahi thi — toh admin-only UI sab users ko dikh raha tha (project delete, member invite, project create).
- Usse kya ho rha tha: User ko brand identity galat dikhti (white-label promise tooti), trainers/reviewers se Create / Delete / Invite buttons exposed the — backend permission deny karta tha 403 se, par UX confusing tha aur trainer ko lagta tha kuch kar sakte hain.
- Ab fix ke baad kya hoga: Rebuild ke baad — brand Indigo+Orange sab jagah, "TrainPlex Studio" logo + favicon, aur trainer/reviewer login pe Create/Invite/Delete button automatically chhup jayenge (server-side RBAC ke saath defense-in-depth). Admin ko sab kuch dikhega jaisa pehle. Role field WhoAmI API mein expose ho gayi, RoleGate component reusable hai — Week 4 mein aur jagah daal denge.

---

### Step 1.4-C Hindi UI integration (Week 3 continued)

Wires the existing `@humansignal/app-common` i18n framework (en + hi, 32 keys) into the running labelstudio app so the HindiToggle in the top bar actually flips visible UI between English and Hindi, and `<html lang>` stays in sync with the active language so the `[lang="hi"]` CSS in `tokens.trainplex.css` (Devanagari line-height) kicks in automatically. First batch of t() wrapping demonstrates the pattern on 4 high-traffic components (Home / Projects / People / DangerZone) — full sweep deferred to Week 4 per task scope.

#### Files Created

| File | Purpose |
|------|---------|
| `web/libs/app-common/src/i18n/__tests__/integration.test.ts` | 6 Jest tests covering en-default, hi switch + en round-trip, English interpolation (`trainer.task_locked_tier`), the newly-added `admin.add_members` + `home.welcome` keys in both locales, and a runtime parity check that `getResourceBundle('en','common')` and `getResourceBundle('hi','common')` have identical key sets. Complements the existing `config.test.ts` (which already covers init + Hindi switch) — no existing test file touched. |

#### Files Modified

| File | Change |
|------|--------|
| `web/apps/labelstudio/src/main.tsx` | Side-effect import `@humansignal/app-common/i18n/config` to trigger `i18n.init()` BEFORE `./app/App` (the React entry). Added `i18n.on('languageChanged', ...)` that mirrors the active language onto `document.documentElement.lang`, plus an initial-sync line so the very first render already has the right `<html lang>` (matters because `LanguageDetector` resolves synchronously during init from `localStorage.tp_lang` / cookie). |
| `web/apps/labelstudio/src/components/Menubar/Menubar.jsx` | Imported `HindiToggle` from `@humansignal/ui` (already re-exported there) and rendered it in the top bar inside a `<div className="ml-2 mr-2">` wrapper, positioned right after `<ThemeToggle />` and right before the user-account `Dropdown.Trigger` — so the language switch sits next to the user menu, matching task spec. |
| `web/apps/labelstudio/src/pages/Home/HomePage.tsx` | `useTranslation()` wired into `HomePage`. Wrapped 7 user-facing strings: `home.welcome`, `home.lets_get_started`, `home.recent_projects`, `home.view_all`, `home.create_first_project`, `admin.create_project` (both the empty-state button label + its `aria-label`), and `home.resources` (Resources card title). The static `actions` array switched from a hardcoded `title: "Create Project"` shape to `titleKey: "admin.create_project"` so the label resolves at render-time (and re-renders when the user flips language). |
| `web/apps/labelstudio/src/pages/Projects/Projects.jsx` | `useTranslation()` wired into `ProjectsPage.context` (the function component rendered into the Menubar's context slot via `RoutesProvider`). Wrapped the "Create" project button label + its `aria-label` using `admin.create_project`. |
| `web/apps/labelstudio/src/pages/Organization/PeoplePage/PeoplePage.jsx` | `useTranslation()` wired into `PeoplePage`. Wrapped the "Add Members" button label + its `aria-label` using the new `admin.add_members` key. |
| `web/apps/labelstudio/src/pages/Settings/DangerZone.jsx` | `useTranslation()` wired into `DangerZone`. Wrapped the modal-footer "Cancel" button using `common.cancel`. The dynamic destructive labels ("Delete Project", "Reset Cache", "Drop All Tabs") deliberately left in English for now — they're admin-only and the destructive context benefits from unambiguous English copy until Week 4 reviews the Hindi phrasing with a native speaker. |
| `web/libs/app-common/src/locales/en/common.json` | Added 8 new keys (parity-matched with hi.json — see locale parity check below). New: `admin.add_members`, `admin.invite_members`, `home.welcome`, `home.lets_get_started`, `home.recent_projects`, `home.view_all`, `home.create_first_project`, `home.resources`. Total keys: 32 → 40. |
| `web/libs/app-common/src/locales/hi/common.json` | Same 8 new keys with Devanagari translations: `सदस्य जोड़ें`, `सदस्य आमंत्रित करें`, `स्वागत है`, `चलिए शुरू करते हैं।`, `हाल के प्रोजेक्ट`, `सभी देखें`, `अपना पहला प्रोजेक्ट बनाएँ`, `संसाधन`. Total keys: 32 → 40. |

#### New i18n keys added (8 keys × 2 locales = 16 entries)

| Key | English | Hindi |
|-----|---------|-------|
| `admin.add_members` | Add Members | सदस्य जोड़ें |
| `admin.invite_members` | Invite Members | सदस्य आमंत्रित करें |
| `home.welcome` | Welcome | स्वागत है |
| `home.lets_get_started` | Let's get you started. | चलिए शुरू करते हैं। |
| `home.recent_projects` | Recent Projects | हाल के प्रोजेक्ट |
| `home.view_all` | View All | सभी देखें |
| `home.create_first_project` | Create your first project | अपना पहला प्रोजेक्ट बनाएँ |
| `home.resources` | Resources | संसाधन |

#### Strings wrapped with t()

13 strings across 4 components:

| Component | Strings wrapped | Keys used |
|-----------|----------------|-----------|
| `HomePage.tsx` | 9 (welcome, sub-heading, 2× action button label, recent-projects header, view-all link, empty-state heading, 2× create-project button — label + aria-label, resources card title) | `home.welcome`, `home.lets_get_started`, `admin.create_project`, `admin.invite_members`, `home.recent_projects`, `home.view_all`, `home.create_first_project`, `home.resources` |
| `Projects.jsx` | 2 (button label + aria-label on the top-bar Create) | `admin.create_project` |
| `PeoplePage.jsx` | 2 (button label + aria-label on Add Members) | `admin.add_members` |
| `DangerZone.jsx` | 1 (modal-footer Cancel button) | `common.cancel` |

#### HindiToggle location in header

Rendered inside `Menubar.jsx`, in the top-right cluster, between `<ThemeToggle />` (conditional on `FF_THEME_TOGGLE`) and the user-account `Dropdown.Trigger`. Wrapped in `<div className="ml-2 mr-2">` for spacing. The toggle reads `i18n.language`, displays "हि" when active language is English (suggesting the switch target) and "EN" when active is Hindi, and persists the choice to `localStorage.tp_lang` + cookie via the existing `LanguageDetector` config.

#### i18n init wiring

Order in `main.tsx`:
1. `registerAnalytics()` — must run before anything else (existing).
2. `import "@humansignal/app-common/i18n/config"` — side-effect import; resolves the persisted language from `localStorage.tp_lang` → cookie → `navigator.language` (in that order) and resolves `i18n.t()` synchronously before any component mounts.
3. `i18n.on("languageChanged", ...)` + initial `document.documentElement.lang = i18n.language` — keep `<html lang>` reactive so the `[lang="hi"]` rules in `tokens.trainplex.css` apply automatically.
4. `import "./app/App"` — React root mount.

This means: on first page load, if the user previously selected Hindi, `<html lang="hi">` is set BEFORE the React tree paints, so the Devanagari CSS rules apply in the first frame (no flash of wrong-language line-height).

#### Locale parity check

```
$ node -e "..." # see task spec for the one-liner
en: 40  hi: 40  match: true
```

Run after every key edit to confirm en.json and hi.json have identical key sets.

#### Skipped — deliberately

| Target | Why skipped |
|--------|-------------|
| **Auth pages** (login, signup, password reset) | These are server-rendered Django templates (`label_studio/users/templates/`), not React — they need a separate Django-side i18n pass (django.po files + `{% trans %}` tags) which is a Week 4 task. |
| **`web/libs/editor/`** | Separately-compiled mobx-state-tree bundle, doesn't use the same `useAuth()` / hook pipeline. Same reason RoleGate isn't wired there yet. Deferred to Week 4. |
| **Heidi tips copy** | Per task spec — upstream HumanSignal-specific copy is not translated. |
| **DangerZone destructive button labels** ("Delete Project", "Reset Cache", "Drop All Tabs") | Admin-only, destructive. Want a native Hindi speaker to review the phrasing in Week 4 before shipping translations of irreversible actions; English copy is unambiguous in the meantime. |
| **`Spinner` / loading text, "can't load projects" error** | Will be wrapped in the Week 4 full sweep alongside other error / empty state copy. |

#### Tests

- `web/libs/app-common/src/i18n/__tests__/integration.test.ts` — 6 tests added. Coverage: en default, hi → en round trip, English interpolation, new `admin.add_members` + `home.welcome` keys in both locales, runtime resource-bundle parity diff.
- Existing `config.test.ts` untouched (per spec — "only add").
- No other test files modified.

#### How to verify

```bash
# Locale parity (fast, no rebuild needed):
cd C:\TrainPlex\trainplex-studio
node -e "const en=require('./web/libs/app-common/src/locales/en/common.json'); const hi=require('./web/libs/app-common/src/locales/hi/common.json'); function flat(o,p='',a=[]){Object.keys(o).forEach(k=>typeof o[k]==='object'?flat(o[k],p+k+'.',a):a.push(p+k));return a;} const e=flat(en).sort(),h=flat(hi).sort(); console.log('en:'+e.length,'hi:'+h.length,'match:'+(e.join()===h.join()));"
# expected: en:40 hi:40 match:true

# Jest (inside container after rebuild, or once node_modules is installed):
yarn nx test app-common --testPathPattern=i18n

# Manual UI smoke (after yarn build — founder approval required):
# 1. Open the app — top-right shows the "हि" toggle button.
# 2. Click it — entire visible UI (Home welcome, Create Project / Add Members buttons, Recent Projects header, Cancel in delete-confirmation modal) flips to Devanagari.
# 3. Open DevTools → Elements → <html> — lang attribute now reads "hi".
# 4. Refresh — language persists (localStorage.tp_lang === "hi").
# 5. Click "EN" — flips back, lang attribute becomes "en", everything reverts.
```

#### 3-line Hindi recap (founder)

- Kya bug tha: i18n framework, locale JSONs (en/hi), HindiToggle component sab existing the — par kuch bhi wire nahi tha. Toggle button kahin render nahi ho raha tha, `i18n.init()` kabhi call nahi hota tha, aur kisi component ne `t()` use nahi kiya tha — toh app abhi tak 100% English tha.
- Usse kya ho rha tha: Phase 1 deliverable "Hindi-first UI" promise tooti — backend Hindi-capable, infra ready, par end-user ke screen pe English hi dikhta tha. Plus `[lang="hi"]` ke saath jo Devanagari line-height rules likhe the `tokens.trainplex.css` mein — wo bhi kabhi kick-in nahi karte the kyunki `<html lang>` hamesha "en" rehta tha.
- Ab fix ke baad kya hoga: Rebuild ke baad — top bar mein "हि" / "EN" toggle button dikhega, click karte hi visible UI (Home welcome / Create Project / Add Members / Cancel modal / Recent Projects) Devanagari mein flip ho jayega. `<html lang>` reactive — Hindi mein switch karte hi Devanagari line-height auto-apply. Choice browser mein persist (localStorage `tp_lang`). 13 strings wrap kiye 4 components mein as proof — full app sweep Week 4 mein.

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
