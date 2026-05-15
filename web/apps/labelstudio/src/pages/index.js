import { ProjectsPage } from "./Projects/Projects";
import { HomePage } from "./Home/HomePage";
import { OrganizationPage } from "./Organization";
import { ModelsPage } from "./Organization/Models/ModelsPage";
import { AuditLogPage } from "./Admin/AuditLog";
import { DashboardWidget } from "./Admin/DashboardWidget";
import { HeatmapPage } from "./Admin/Heatmap";
import { ProjectWizard } from "./Admin/ProjectWizard";
import { WhatsAppBroadcastPage } from "./Admin/WhatsAppBroadcast";
import { TwoFactorSetup } from "./Settings/TwoFactor/TwoFactorSetup";
import { TwoFactorDisable } from "./Settings/TwoFactor/TwoFactorDisable";
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
  // TrainPlex Phase 1 Step 12.4 — 2FA enrollment + disable Settings pages.
  // RoleGate inside each component restricts to admin + qa_lead. The
  // login-step challenge component (TwoFactorChallenge) is rendered from
  // the password-form page on receipt of {requires_2fa:true}; no static
  // route entry needed because it lives in the unauthenticated flow.
  TwoFactorSetup,
  TwoFactorDisable,
  pages.AccountSettingsPage,
].filter(Boolean);
