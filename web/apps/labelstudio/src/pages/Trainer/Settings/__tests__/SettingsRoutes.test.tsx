/**
 * Route metadata + RoleGate fallback tests for the trainer Settings pages.
 *
 * Each Settings page exports `Page` metadata (`.path`, `.exact`) so the
 * router registry in `pages/index.js` picks them up. We assert both the
 * path string and that a non-trainer (admin/reviewer) is denied via the
 * RoleGate fallback.
 *
 * Phase 1 Step 13.
 */

/* eslint-disable @typescript-eslint/no-var-requires */

import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import React from "react";

jest.mock("../../../../providers/ApiProvider", () => ({
  useAPI: () => ({ callApi: jest.fn() }),
  ApiContext: { Provider: ({ children }: any) => children },
}));

let mockUserRole: string | null = "trainer";
const setMockRole = (role: string | null) => {
  mockUserRole = role;
};
jest.mock("@humansignal/core/providers/AuthProvider", () => ({
  useAuth: () => ({ user: { role: mockUserRole } }),
}));

jest.mock("@tanstack/react-query", () => ({
  useQuery: () => ({ data: undefined, isFetching: true, isError: false }),
  useMutation: () => ({ mutate: jest.fn(), isPending: false }),
  useQueryClient: () => ({ invalidateQueries: jest.fn() }),
}));

jest.mock("@humansignal/app-common", () => ({
  useTranslation: () => ({
    t: (key: string) => key,
    i18n: { language: "en" },
  }),
}));

import { NotificationsPage } from "../NotificationsPage";
import { PayoutPage } from "../PayoutPage";
import { PreferencesPage } from "../PreferencesPage";
import { ProfilePage } from "../ProfilePage";
import { SecurityPage } from "../SecurityPage";

const pages: Array<{
  name: string;
  Component: React.FC;
  path: string;
  forbiddenTestId: string;
}> = [
  { name: "ProfilePage", Component: ProfilePage as any, path: "/trainer/settings/profile", forbiddenTestId: "profile-forbidden" },
  { name: "SecurityPage", Component: SecurityPage as any, path: "/trainer/settings/security", forbiddenTestId: "security-forbidden" },
  { name: "NotificationsPage", Component: NotificationsPage as any, path: "/trainer/settings/notifications", forbiddenTestId: "notifications-forbidden" },
  { name: "PayoutPage", Component: PayoutPage as any, path: "/trainer/settings/payout", forbiddenTestId: "payout-forbidden" },
  { name: "PreferencesPage", Component: PreferencesPage as any, path: "/trainer/settings/preferences", forbiddenTestId: "preferences-forbidden" },
];

describe("Trainer settings — route metadata", () => {
  pages.forEach(({ name, Component, path }) => {
    it(`${name} exposes ${path} as its route path`, () => {
      expect((Component as any).path).toBe(path);
      expect((Component as any).exact).toBe(true);
    });
  });
});

describe("Trainer settings — RoleGate fallback", () => {
  beforeEach(() => setMockRole("trainer"));

  pages.forEach(({ name, Component, forbiddenTestId }) => {
    it(`${name} hides content from non-trainer (admin) users`, () => {
      setMockRole("admin");
      render(
        <MemoryRouter>
          <Component />
        </MemoryRouter>,
      );
      expect(screen.getByTestId(forbiddenTestId)).toBeInTheDocument();
    });

    it(`${name} hides content from non-trainer (reviewer) users`, () => {
      setMockRole("reviewer");
      render(
        <MemoryRouter>
          <Component />
        </MemoryRouter>,
      );
      expect(screen.getByTestId(forbiddenTestId)).toBeInTheDocument();
    });
  });
});
