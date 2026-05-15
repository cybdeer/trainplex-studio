import { ProjectsPage } from "./Projects/Projects";
import { HomePage } from "./Home/HomePage";
import { OrganizationPage } from "./Organization";
import { ModelsPage } from "./Organization/Models/ModelsPage";
import { DashboardWidget } from "./Admin/DashboardWidget";
import { ProjectWizard } from "./Admin/ProjectWizard";
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
  // TrainPlex Phase 1 Step 12.4 — 2FA enrollment + disable Settings pages.
  // RoleGate inside each component restricts to admin + qa_lead. The
  // login-step challenge component (TwoFactorChallenge) is rendered from
  // the password-form page on receipt of {requires_2fa:true}; no static
  // route entry needed because it lives in the unauthenticated flow.
  TwoFactorSetup,
  TwoFactorDisable,
  pages.AccountSettingsPage,
].filter(Boolean);
