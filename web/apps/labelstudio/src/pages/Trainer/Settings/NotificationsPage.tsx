/**
 * NotificationsPage — WA / email / SMS / push toggles + quiet-hours +
 * frequency cap.
 *
 * Per plan Step 13: trainer chooses how we reach them. Backend stores
 * the prefs under `profile.notification_prefs`; the React form serializes
 * the whole object on every change (debounced via the mutate call).
 *
 * Phase 1 Step 13.
 */

import { RoleGate, Spinner } from "@humansignal/ui";
import { useTranslation } from "@humansignal/app-common";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { useAPI } from "../../../providers/ApiProvider";
import type { Page } from "../../types/Page";
import { SettingsLayout } from "./SettingsLayout";
import type { NotificationPrefs, TrainerProfile } from "./types";
import styles from "./Settings.module.css";

const PROFILE_QUERY_KEY = "trainer-profile";

interface ToggleProps {
  testId: string;
  on: boolean;
  onChange: (next: boolean) => void;
  label: string;
  description?: string;
}

function ToggleRow({ testId, on, onChange, label, description }: ToggleProps) {
  return (
    <div className={styles.toggleRow}>
      <div>
        <div className={styles.toggleLabel}>{label}</div>
        {description && <div className={styles.toggleDescription}>{description}</div>}
      </div>
      <button
        type="button"
        className={styles.toggleSwitch}
        data-on={on ? "true" : "false"}
        data-testid={testId}
        aria-pressed={on}
        aria-label={label}
        onClick={() => onChange(!on)}
      >
        <span className={styles.toggleKnob} />
      </button>
    </div>
  );
}

export const NotificationsPage: Page = () => {
  const api = useAPI();
  const { t } = useTranslation();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const [savedFlash, setSavedFlash] = useState(false);

  const { data: profile, isFetching, isError } = useQuery<TrainerProfile>({
    queryKey: [PROFILE_QUERY_KEY],
    queryFn: async () => {
      const res = await api.callApi("trainerProfile");
      return res as TrainerProfile;
    },
    enabled: user?.role === "trainer",
  });

  const [prefs, setPrefs] = useState<NotificationPrefs>({
    wa: true,
    email: true,
    sms: false,
    push: true,
    quiet_hours: true,
    frequency_limit: true,
  });

  useEffect(() => {
    if (profile?.notification_prefs) setPrefs(profile.notification_prefs);
  }, [profile]);

  const save = useMutation({
    mutationFn: async (next: NotificationPrefs) => {
      return api.callApi("trainerProfileUpdate", {
        body: { notification_prefs: next },
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [PROFILE_QUERY_KEY] });
      setSavedFlash(true);
      setTimeout(() => setSavedFlash(false), 1500);
    },
  });

  const onToggle = (key: keyof NotificationPrefs) => (next: boolean) => {
    const updated = { ...prefs, [key]: next };
    setPrefs(updated);
    save.mutate(updated);
  };

  return (
    <RoleGate
      allow={["trainer"]}
      userRole={user?.role}
      fallback={
        <div className={styles.errorBox} data-testid="notifications-forbidden">
          403 — trainer only
        </div>
      }
    >
      <SettingsLayout>
        <h1 className={styles.pageTitle}>{t("trainer.settings.notifications")}</h1>

        {isFetching && !profile ? (
          <div className={styles.loadingBox} data-testid="notifications-loading">
            <Spinner />
          </div>
        ) : isError ? (
          <div className={styles.errorBox}>{t("common.error")}</div>
        ) : (
          <div data-testid="notifications-form">
            <p style={{ fontSize: 13, color: "#6b7280", marginBottom: 12 }}>
              {t("trainer.notifications.description")}
            </p>
            <ToggleRow
              testId="toggle-wa"
              on={prefs.wa}
              onChange={onToggle("wa")}
              label={t("trainer.notifications.wa")}
            />
            <ToggleRow
              testId="toggle-email"
              on={prefs.email}
              onChange={onToggle("email")}
              label={t("trainer.notifications.email")}
            />
            <ToggleRow
              testId="toggle-sms"
              on={prefs.sms}
              onChange={onToggle("sms")}
              label={t("trainer.notifications.sms")}
            />
            <ToggleRow
              testId="toggle-push"
              on={prefs.push}
              onChange={onToggle("push")}
              label={t("trainer.notifications.push")}
            />
            <ToggleRow
              testId="toggle-quiet-hours"
              on={prefs.quiet_hours}
              onChange={onToggle("quiet_hours")}
              label={t("trainer.notifications.quiet_hours")}
            />
            <ToggleRow
              testId="toggle-frequency-limit"
              on={prefs.frequency_limit}
              onChange={onToggle("frequency_limit")}
              label={t("trainer.notifications.frequency_limit")}
            />
            {savedFlash && (
              <div className={styles.savedNote} data-testid="notifications-saved-flash">
                {t("trainer.settings.saved")}
              </div>
            )}
          </div>
        )}
      </SettingsLayout>
    </RoleGate>
  );
};

NotificationsPage.title = "Notifications";
NotificationsPage.path = "/trainer/settings/notifications";
NotificationsPage.exact = true;

export default NotificationsPage;
