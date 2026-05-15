/**
 * RoleGate — render children only when the current user's role is in the
 * `allow` list.
 *
 * TrainPlex Studio Phase 1 Step 1.4-B (RBAC frontend gating).
 *
 * Pull `userRole` from your app store / WhoAmI response. The component is
 * presentational only — it does NOT enforce server-side authorization (the
 * backend already does that via DRF permissions). RoleGate exists purely to
 * hide elements that the user has no business clicking; bypassing it in the
 * DOM still gets you a 403 from the API.
 *
 * Example:
 *   <RoleGate allow={['admin']} userRole={user?.role}>
 *     <DeleteProjectButton />
 *   </RoleGate>
 */

import type { ReactNode } from "react";

export type Role = "trainer" | "reviewer" | "qa_lead" | "admin";

export interface RoleGateProps {
  /** Hide children unless `userRole` is in this list. */
  allow: Role[];
  /** Current user role from your app store / WhoAmI response. */
  userRole?: Role | string | null;
  /** Element(s) to gate. */
  children: ReactNode;
  /** Optional fallback rendered when blocked. Defaults to null. */
  fallback?: ReactNode;
}

export function RoleGate({ allow, userRole, children, fallback = null }: RoleGateProps) {
  if (!userRole) return <>{fallback}</>;
  return allow.includes(userRole as Role) ? <>{children}</> : <>{fallback}</>;
}
