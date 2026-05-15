import { ProjectsPage } from "./Projects/Projects";
import { HomePage } from "./Home/HomePage";
import { OrganizationPage } from "./Organization";
import { ModelsPage } from "./Organization/Models/ModelsPage";
import { DashboardWidget } from "./Admin/DashboardWidget";
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
  pages.AccountSettingsPage,
].filter(Boolean);
