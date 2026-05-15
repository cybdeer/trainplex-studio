import type { Ability } from "../providers/AuthProvider";

/** TrainPlex Studio role values (Phase 1 Step 1.4-B). */
export type TrainPlexRole = "trainer" | "reviewer" | "qa_lead" | "admin";

export type APIUser = {
  id: number;
  first_name: string;
  last_name: string;
  username: string;
  email: string;
  last_activity: string;
  avatar: string | null;
  initials: string;
  phone: string;
  active_organization: number;
  active_organization_meta: {
    title: string;
    email: string;
  };
  allow_newsletters: boolean;
  date_joined: string;
  permissions?: Ability[];
  /** TrainPlex RBAC role, exposed by BaseUserSerializer (Step 1.4-B). */
  role?: TrainPlexRole;
};
