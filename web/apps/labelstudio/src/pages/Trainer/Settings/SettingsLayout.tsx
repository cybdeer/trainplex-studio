/**
 * SettingsLayout — sidebar nav + content container shared by all 5
 * trainer settings pages (Profile / Security / Notifications / Payout /
 * Preferences).
 *
 * Sidebar is sticky on >= 768px (matches the existing AccountSettings
 * pattern). On narrow screens it collapses to a horizontal pill row.
 *
 * Phase 1 Step 13.
 */

import { useTranslation } from "@humansignal/app-common";
import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";
import styles from "./Settings.module.css";

interface NavItem {
  to: string;
  i18nKey: string;
  testId: string;
}

const NAV: NavItem[] = [
  { to: "/trainer/settings/profile", i18nKey: "trainer.settings.profile", testId: "nav-profile" },
  { to: "/trainer/settings/security", i18nKey: "trainer.settings.security", testId: "nav-security" },
  {
    to: "/trainer/settings/notifications",
    i18nKey: "trainer.settings.notifications",
    testId: "nav-notifications",
  },
  { to: "/trainer/settings/payout", i18nKey: "trainer.settings.payout", testId: "nav-payout" },
  {
    to: "/trainer/settings/preferences",
    i18nKey: "trainer.settings.preferences",
    testId: "nav-preferences",
  },
];

export interface SettingsLayoutProps {
  children: ReactNode;
}

export function SettingsLayout({ children }: SettingsLayoutProps) {
  const { t } = useTranslation();
  return (
    <div className={styles.settingsRoot} data-testid="trainer-settings-root">
      <aside className={styles.sidebar} data-testid="trainer-settings-sidebar">
        <div className={styles.sidebarHeading}>{t("trainer.settings.sidebar_heading")}</div>
        <nav className={styles.sidebarNav}>
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              data-testid={item.testId}
              className={({ isActive }) =>
                isActive
                  ? `${styles.sidebarLink} ${styles.sidebarLinkActive}`
                  : styles.sidebarLink
              }
            >
              {t(item.i18nKey)}
            </NavLink>
          ))}
        </nav>
      </aside>
      <section className={styles.contentCard}>{children}</section>
    </div>
  );
}

export { NAV as SETTINGS_NAV };
