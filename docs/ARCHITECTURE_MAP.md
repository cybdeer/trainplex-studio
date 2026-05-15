# TrainPlex Studio — Architecture Map

Generated: 2026-05-15 (Week 1, Phase 1 Step 1.3)

Maps Label Studio (`develop` branch) structure to TrainPlex customization priorities.

---

## High-Level Layout

```
trainplex-studio/
├── label_studio/        Django backend (Python)
├── web/
│   ├── apps/
│   │   ├── labelstudio/ Main app shell (React + TypeScript)
│   │   └── playground/  XML config preview tool
│   └── libs/
│       ├── app-common/  Shared UI utilities
│       ├── core/        Core React lib
│       ├── datamanager/ Task list / DataManager UI (★ kill admin elements here)
│       ├── editor/      Annotation editor canvas
│       ├── ui/          Shared UI components
│       └── frontend-test/ Playwright e2e
├── deploy/              nginx + Postgres configs
├── docs/                Documentation (this file)
└── tools/               Build helpers
```

---

## Backend — Django apps (`label_studio/`)

| App | Purpose | Key models |
|-----|---------|-----------|
| `core` | Settings, base URLs, feature flags, utils | — |
| `users` | User auth (email-based) | `User` (AbstractBaseUser + PermissionsMixin) |
| `organizations` | Multi-tenancy roots | `Organization`, `OrganizationMember` |
| `projects` | Project model + XML config | `Project`, `ProjectMember`, `ProjectSummary` |
| `tasks` | Tasks + Annotations | `Task`, `Annotation`, `Prediction`, `AnnotationDraft` |
| `data_manager` | Filtered task list views | `View`, `Filter`, `FilterGroup` |
| `data_import` | CSV/JSON/file upload | — |
| `data_export` | Export annotations | `Export`, `ConvertedFormat` |
| `io_storages` | S3/GCS/Azure/local storage | `S3ImportStorage`, etc. |
| `labels_manager` | Label set management | `Label` |
| `ml` / `ml_models` / `ml_model_providers` | ML backends (auto-label) | `MLBackend`, `MLBackendTrainJob` |
| `webhooks` | External event subscriptions | `Webhook`, `WebhookAction` |
| `jwt_auth` | JWT token issue/refresh | `LSAPIToken`, `LSTokenBlacklistedToken` |
| `session_policy` | Session timeout config | `SessionPolicy` |
| `fsm` | Finite state machines for workflows | — |

### URL routing roots
- `label_studio/core/urls.py` — root URL conf, includes all sub-app URLs
- Each app has its own `urls.py` (15 total)

---

## Frontend — `web/`

### Main app shell: `web/apps/labelstudio/`
Entry: `src/main.tsx` → `src/App.tsx`

Key pages:
- `Home/HomePage.tsx`
- `CreateProject/` — project setup wizard
- `Organization/PeoplePage` — team management
- `Organization/Models/` — ML backend management
- `Settings/StorageSettings/` — storage providers
- `Projects/` — project list + dashboard

Key providers:
- `ApiProvider.tsx` — API client context
- `AppStoreProvider.tsx` — MobX store
- `ProjectProvider.tsx` — current project context

### Libs

| Lib | Purpose | Key files |
|-----|---------|-----------|
| `web/libs/datamanager` | Task list table UI | DataManager.jsx |
| `web/libs/editor` | Annotation editor canvas | LabelStudio.js entry |
| `web/libs/app-common` | Shared utilities | — |
| `web/libs/core` | Core React abstractions | — |
| `web/libs/ui` | UI primitives (buttons, modals) | — |
| `web/libs/frontend-test` | Playwright e2e tests | — |

---

## Customization Targets — Phase 1 Priorities

### A. RBAC Built-in (Step 1.4-A, Step 3.5)
**Backend:**
- `label_studio/users/models.py` — extend `User` with `role` enum field (trainer/reviewer/qa_lead/admin)
- New file: `label_studio/users/middleware/rbac.py` — `@require_role()` decorator
- `label_studio/users/permissions.py` (new) — DRF permission classes per role

**Frontend:**
- `web/apps/labelstudio/src/providers/AppStoreProvider.tsx` — store role in app state
- New file: `web/libs/ui/src/components/RoleGate.tsx` — conditional render by role

**Migration:**
- `label_studio/users/migrations/0XXX_add_role_field.py`

---

### B. Admin Elements Removed Code-Level (Step 1.4-B)
**Frontend (most work here):**
- `web/libs/datamanager/src/components/DataManager.jsx` — remove top dropdown for trainer role
- `web/libs/datamanager/src/components/CellViews/` — remove delete action
- `web/apps/labelstudio/src/components/Modal/` — strip admin-only modals
- `web/apps/labelstudio/src/pages/Settings/` — hide settings for non-admin

**Backend (defense in depth):**
- `label_studio/projects/api.py` — block delete project for non-admin
- `label_studio/tasks/api.py` — block delete annotation for non-admin

---

### C. Devanagari UI / i18n (Step 1.4-C, Step 15)
**Frontend:**
- New: `web/libs/app-common/src/i18n/config.ts` — react-i18next setup
- New: `web/libs/app-common/src/locales/en.json` — English baseline
- New: `web/libs/app-common/src/locales/hi.json` — Hindi translations
- Replace hard-coded strings across all `.tsx` files with `t('key')` calls

**Backend:**
- `label_studio/core/settings/label_studio.py` — enable Django i18n middleware
- New: `label_studio/locale/hi/LC_MESSAGES/django.po` — Hindi server-side translations
- Error message constants → `_('English text')` wrapping

---

### D. TrainPlex Branding (Step 1.4-D)
**Frontend:**
- `web/libs/ui/src/tokens.css` (new) — define `--brand-indigo: #1A1A5E; --brand-orange: #FF6B35;`
- `web/apps/labelstudio/src/main.tsx` — import tokens.css
- Logo SVG: `web/apps/labelstudio/public/logo.svg` — replace Label Studio logo with TrainPlex
- `web/apps/labelstudio/src/components/Topbar/` — header branding
- Favicon: `web/apps/labelstudio/public/favicon.ico`

**Tailwind config (if added):**
- `web/tailwind.config.js` (new) — extend theme with TrainPlex tokens

---

### E. Batch Flow Native — 10-task batch view (Step 1.4-E, Step 4.1)
**Backend:**
- New: `label_studio/tasks/api/batch.py` — endpoint `/api/tasks/batch/?size=10`
- New: `label_studio/tasks/services/batch_assigner.py` — assign-then-lock logic

**Frontend:**
- New: `web/apps/labelstudio/src/pages/Trainer/BatchView.tsx` — trainer batch screen
- New: `web/libs/ui/src/components/TaskQueueCard.tsx`
- New: `web/libs/ui/src/components/EarningsTicker.tsx`
- New: `web/libs/ui/src/components/TierBadge.tsx`

**Models extension:**
- `label_studio/tasks/models.py` — add `Batch` model (FK to user + tasks list + lock_until)

---

### F. Peer Review Native — 3-reviewer consensus (Step 1.4-F, Step 6)
**Backend:**
- New: `label_studio/peer_review/` (new Django app)
  - `models.py` — `ReviewAssignment`, `Review`, `ConsensusResult`, `Dispute`
  - `services/consensus_engine.py` — 3/3, 2/3, 1/3, 0/3 logic
  - `services/reviewer_assigner.py` — tier + language match + cooldown
  - `api.py` — reviewer queue, submit review, QA disputes
  - `urls.py`

**Migrations:**
- `peer_review/migrations/0001_initial.py`

**Frontend:**
- New: `web/apps/labelstudio/src/pages/Reviewer/Queue.tsx`
- New: `web/apps/labelstudio/src/pages/Reviewer/ReviewTask.tsx`
- New: `web/libs/ui/src/components/ReviewSplitView.tsx`
- New: `web/libs/ui/src/components/ConsensusIndicator.tsx`

---

### G. Submit-for-Review — Payment Hold (Step 1.4-G, Step 6.4)
**Backend:**
- `label_studio/tasks/models.py` — extend `Annotation` with `payment_status` (hold/approved/released/disputed)
- New: `label_studio/payments/` (new app)
  - `models.py` — `PaymentHold`, `PayoutQueue`, `WalletTransaction`
  - `services/razorpay_handler.py` — UPI payout integration
  - `services/payout_cron.py` — daily/weekly auto-release

**Frontend:**
- New: `web/apps/labelstudio/src/pages/Trainer/Wallet.tsx`
- New: `web/libs/ui/src/components/PaymentStatusBadge.tsx`

---

## Authentication Flow (current LS, to simplify Step 3)

Current LS auth:
1. Browser → `/user/login/` (Django) → email + password
2. Django sets session cookie
3. DRF Token (`rest_framework.authtoken.Token`) for API
4. JWT tokens (`jwt_auth` app) for SDK access

TrainPlex Fork simplification (Step 3):
- Unified JWT (no separate session cookie + DRF token + JWT)
- HttpOnly cookie with SameSite=Lax
- Drop session-based auth completely

---

## Feature Flags (LS-internal, keep for now)

`label_studio/core/feature_flags/`:
- LaunchDarkly SDK integration
- `flag_set('flag_name', user='auto')` pattern across codebase
- TrainPlex will likely replace with simpler in-house flag (Step 17.8)

---

## Quick-Win Files to Touch First (Week 1-2)

1. `label_studio/users/models.py` → add `role` field (RBAC foundation)
2. `web/libs/ui/src/tokens.css` (new) → TrainPlex colors
3. `web/apps/labelstudio/public/logo.svg` → replace logo
4. `web/libs/app-common/src/i18n/config.ts` (new) → i18n bootstrap
5. `label_studio/core/settings/label_studio.py` → enable Django i18n middleware

These 5 files unblock Weeks 2-3 work (RBAC + Hindi + branding).

---

## Risk Flags — Tightly Coupled Areas

⚠️ **DataManager.jsx** — Single 1000+ line component, heavy MobX state. Customizing admin removal is fragile. Mitigation: wrap with role-aware render guards instead of deleting code paths.

⚠️ **Editor canvas (`web/libs/editor`)** — Konva-based canvas with deep MST (mobx-state-tree) state. Don't touch internals; wrap externally for TrainPlex annotator shell.

⚠️ **Settings module** — Many tabs, deeply nested. Risk of breaking when hiding admin tabs. Mitigation: feature-flag visibility per tab.

⚠️ **Organization model** — Multi-tenancy already exists in LS. Reusing it for TrainPlex org isolation should be straightforward, but watch for invitation flow assumptions.

---

## Out of Scope for Week 1-2

- ML model backend integration (`ml*` apps) — defer Phase 2
- WebSocket / real-time updates — current LS uses polling, keep for now
- LaunchDarkly replacement — replace with simple in-house in Step 17.8
- Mobile app — Phase 2 Step 10 (deferred)

---

## Cross-Reference

| Plan Step | Files (quick-jump) |
|-----------|---------------------|
| Step 1.4-A RBAC | `label_studio/users/models.py`, new `middleware/rbac.py` |
| Step 1.4-B Admin remove | `web/libs/datamanager/src/components/DataManager.jsx`, `web/apps/labelstudio/src/pages/Settings/*` |
| Step 1.4-C Hindi | `web/libs/app-common/src/i18n/` (new), all `.tsx` strings |
| Step 1.4-D Branding | `web/libs/ui/src/tokens.css` (new), `web/apps/labelstudio/public/logo.svg` |
| Step 1.4-E Batch | `label_studio/tasks/api/batch.py` (new), `web/apps/labelstudio/src/pages/Trainer/BatchView.tsx` (new) |
| Step 1.4-F Peer review | `label_studio/peer_review/` (new app), `web/apps/labelstudio/src/pages/Reviewer/` (new) |
| Step 1.4-G Payment hold | `label_studio/payments/` (new app), `web/libs/ui/src/components/PaymentStatusBadge.tsx` (new) |

---

## Notes for Future Sessions

- Always run `make docker-run-dev` (or `docker compose up --build`) from repo root
- Frontend HMR: `cd web && yarn run dev` (after first `yarn install`)
- Backend dev: `make run-dev` requires Poetry installed locally
- Tests: `make test` (uses Sqlite, no Postgres needed)
- Pre-commit hooks: `make configure-hooks` once, then `make fmt` before commit
