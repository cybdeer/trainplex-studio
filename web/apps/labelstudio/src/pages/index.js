import { ProjectsPage } from "./Projects/Projects";
import { HomePage } from "./Home/HomePage";
import { OrganizationPage } from "./Organization";
import { ModelsPage } from "./Organization/Models/ModelsPage";
import { AuditLogPage } from "./Admin/AuditLog";
import { BulkAssignPage } from "./Admin/BulkAssign";
import { DashboardWidget } from "./Admin/DashboardWidget";
import { HeatmapPage } from "./Admin/Heatmap";
import { ProjectWizard } from "./Admin/ProjectWizard";
import { PaymentStatusPage } from "./Admin/PaymentStatus";
import { QualityAlertsPage } from "./Admin/QualityAlerts";
import { WhatsAppBroadcastPage } from "./Admin/WhatsAppBroadcast";
// TrainPlex Phase 1 Step 6 — Reviewer (queue + split-screen review form +
// self-service stats) and QA-lead (dispute queue + three-way resolution)
// surfaces. RoleGate inside each component scopes access; backend mirrors
// via @require_role(['reviewer']) / @require_role(['qa_lead']).
import {
  MyStats as ReviewerMyStats,
  ReviewerDashboard,
  ReviewQueue,
  ReviewSplitScreen,
} from "./Reviewer";
import { DisputeQueue, DisputeResolution } from "./QA";
import { TwoFactorSetup } from "./Settings/TwoFactor/TwoFactorSetup";
import { TwoFactorDisable } from "./Settings/TwoFactor/TwoFactorDisable";
import { BatchPage } from "./Trainer/Batch";
import {
  NotificationsPage,
  PayoutPage,
  PreferencesPage,
  ProfilePage,
  SecurityPage,
} from "./Trainer/Settings";
import { WalletPage } from "./Trainer/Wallet";
import { FF_HOMEPAGE, isFF } from "../utils/feature-flags";
import { pages } from "@humansignal/app-common";

export const Pages = [
  isFF(FF_HOMEPAGE) && HomePage,
  ProjectsPage,
  OrganizationPage,
  ModelsPage,
  // TrainPlex Phase 1 Step 4.2-1 — admin dashboard widget at /admin/dashboard.
  // Component internally gates with <RoleGate allow={['admin']}>, so non-admins
  // who hit the URL directly see a 403 surface (and the API also enforces it).
  DashboardWidget,
  // TrainPlex Phase 1 Step 4.2-2 — admin 3-step Project Wizard at
  // /admin/projects/new. Same RoleGate pattern; backend endpoints are also
  // admin-only via @require_role(['admin']).
  ProjectWizard,
  // TrainPlex Phase 1 Step 4.2-4 — Admin Audit Log viewer at /admin/audit.
  // Reads users.AuditLog rows written by the Step 12.3 hooks (login,
  // role-change, delete). RoleGate('admin') + backend @require_role enforced.
  AuditLogPage,
  // TrainPlex Phase 1 Step 4.2-6 — Admin India activity heatmap at
  // /admin/heatmap. State-wise active trainers + submissions + earnings
  // with intensity colouring (dark Indigo = zyada activity). Same RoleGate
  // + backend @require_role(['admin']) pattern. Mock data in Phase 1;
  // real aggregation lands in Phase 2 / Step 8.
  HeatmapPage,
  // TrainPlex Phase 1 Step 4.2-7 — Admin WhatsApp Broadcast at /admin/wa/broadcast.
  // Picker → trainer filter → preview → send (mock AiSensy). Same RoleGate +
  // backend @require_role(['admin']) pattern. Real AiSensy call lands Week 8.
  WhatsAppBroadcastPage,
  // TrainPlex Phase 1 Step 4.2-3 — Admin Bulk Task Assign at /admin/bulk-assign.
  // Filter trainers (state/tier/language/cert) → assign tasks in bulk
  // (mock plan in Phase 1). Same RoleGate + backend @require_role(['admin'])
  // pattern. Rate-limited to 5 bulk-assigns / hr / admin. Real LS task wiring
  // lands Phase 2 / Step 8.
  BulkAssignPage,
  // TrainPlex Phase 1 Step 4.2-8 — Admin Quality Alert Center at
  // /admin/quality-alerts. Surfaces auto-flagged reviewer-disagreement /
  // time-anomaly / duplicate-pattern signals; admin can filter, drill in,
  // and resolve (reviewed / dismissed / action_taken) with notes. Same
  // RoleGate('admin') + backend @require_role(['admin']) pattern. Detection
  // hooks are MOCK in Phase 1; real call-sites land Week 5 with peer-review.
  QualityAlertsPage,
  // TrainPlex Phase 1 Step 6.4 + 4.2-5 — Admin Payment Status at
  // /admin/payment-status. Per-task hold / released / disputed / refunded
  // table with status-coloured badges (held=orange, released=green,
  // disputed=red, refunded=grey). PayoutQueueDrawer surfaces pending
  // Razorpay payouts + manual retry. RoleGate('admin') + backend
  // @require_role(['admin']) pattern. Razorpay X is MOCKED in Phase 1.
  PaymentStatusPage,
  // TrainPlex Phase 1 Step 12.4 — 2FA enrollment + disable Settings pages.
  // RoleGate inside each component restricts to admin + qa_lead. The
  // login-step challenge component (TwoFactorChallenge) is rendered from
  // the password-form page on receipt of {requires_2fa:true}; no static
  // route entry needed because it lives in the unauthenticated flow.
  TwoFactorSetup,
  TwoFactorDisable,
  // TrainPlex Phase 1 Step 1.4-E — trainer 10-task Batch view at
  // /trainer/batch. RoleGate restricts to ``trainer``; backend
  // @require_role(['trainer']) on GET /api/v1/trainer/batch enforces
  // the same. Mock data Phase 1; real assignment engine Phase 2.
  BatchPage,
  // TrainPlex Phase 1 Step 13 — trainer self-service settings.
  // 5 pages share a sidebar (SettingsLayout): /trainer/settings/{profile,
  // security, notifications, payout, preferences}. Each component gates
  // with <RoleGate allow={['trainer']}>. The profile endpoint silently
  // drops role + email so a trainer cannot self-promote via the form.
  ProfilePage,
  SecurityPage,
  NotificationsPage,
  PayoutPage,
  PreferencesPage,
  // TrainPlex Phase 1 Step 6.4 — Trainer Wallet at /trainer/wallet.
  // Surfaces available balance, held balance, this-month earnings, and
  // recent 30 wallet ledger rows. Trainer-only; backend
  // @require_role(['trainer']) on /api/v1/payments/wallet ensures the
  // trainer can only fetch their own wallet (no ?user_id= query).
  // Cross-references /trainer/settings/payout for UPI setup.
  WalletPage,
  // TrainPlex Phase 1 Step 6 — Reviewer surfaces.
  // /reviewer/dashboard, /reviewer/queue, /reviewer/review/:task_id, /reviewer/stats.
  // Each wraps with <RoleGate allow={['reviewer']}>. Backend enforces via
  // @require_role(['reviewer']) on every endpoint. Payment release wiring
  // (off ConsensusResult.status) is Step 6.4 — next agent's job.
  ReviewerDashboard,
  ReviewQueue,
  ReviewSplitScreen,
  ReviewerMyStats,
  // TrainPlex Phase 1 Step 6 — QA-lead surfaces.
  // /qa/disputes (list) and /qa/disputes/:dispute_id (three-way + resolve).
  // RoleGate('qa_lead') + backend @require_role(['qa_lead']) enforced.
  DisputeQueue,
  DisputeResolution,
  pages.AccountSettingsPage,
].filter(Boolean);
