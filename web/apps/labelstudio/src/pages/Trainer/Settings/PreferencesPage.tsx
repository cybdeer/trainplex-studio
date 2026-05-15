/**
 * PreferencesPage — language toggle, font size, low-data mode, voice-input
 * default.
 *
 * Per plan Step 13. Language uses HindiToggle if available; otherwise a
 * simple two-option radio. Font size + low-data mode persist to the
 * profile meta so the rest of the app can read them.
 *
 * Phase 1 Step 13.
 */

import { HindiToggle, RoleGate, Spinner } from "@humansignal/ui";
import { useTranslation } from "@humansignal/app-common";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { useAPI } from "../../../providers/ApiProvider";
import type { Page } from "../../types/Page";
import { SettingsLayout } from "./SettingsLayout";
import type { FontSize, TrainerProfile } from "./types";
import styles from "./Settings.module.css";

const PROFILE_QUERY_KEY = "trainer-profile";

const FONT_OPTIONS: Array<{ value: FontSize; i18nKey: string; testId: string }> = [
  { value: "small", i18nKey: "trainer.preferences.font_small", testId: "font-small" },
  { value: "medium", i18nKey: "trainer.preferences.font_medium", testId: "font-medium" },
  { value: "large", i18nKey: "trainer.preferences.font_large", testId: "font-large" },
];

export const PreferencesPage: Page = () => {
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

  const [fontSize, setFontSize] = useState<FontSize>("medium");
  const [lowData, setLowData] = useState(false);
  const [voiceDefault, setVoiceDefault] = useState(false);

  useEffect(() => {
    if (!profile) return;
    // Font / low-data / voice live inside notification_prefs meta if the
    // backend ever extends the contract; for now we read from the wider
    // payout_settings or default. We store them in the profile JSON
    // namespace via the PATCH endpoint.
    const meta = (profile as unknown as Record<string, unknown>).preferences as
      | { font_size?: FontSize; low_data?: boolean; voice_default?: boolean }
      | undefined;
    if (meta?.font_size) setFontSize(meta.font_size);
    if (typeof meta?.low_data === "boolean") setLowData(meta.low_data);
    if (typeof meta?.voice_default === "boolean") setVoiceDefault(meta.voice_default);
  }, [profile]);

  const save = useMutation({
    mutationFn: async (payload: Record<string, unknown>) => {
      return api.callApi("trainerProfileUpdate", { body: payload });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [PROFILE_QUERY_KEY] });
      setSavedFlash(true);
      setTimeout(() => setSavedFlash(false), 1500);
    },
  });

  const persist = (updates: Record<string, unknown>) => {
    save.mutate(updates);
  };

  return (
    <RoleGate
      allow={["trainer"]}
      userRole={user?.role}
      fallback={
        <div className={styles.errorBox} data-testid="preferences-forbidden">
          403 — trainer only
        </div>
      }
    >
      <SettingsLayout>
        <h1 className={styles.pageTitle}>{t("trainer.settings.preferences")}</h1>

        {isFetching && !profile ? (
          <div className={styles.loadingBox} data-testid="preferences-loading">
            <Spinner />
          </div>
        ) : isError ? (
          <div className={styles.errorBox}>{t("common.error")}</div>
        ) : (
          <div data-testid="preferences-form">
            <div style={{ marginBottom: 24 }} data-testid="preferences-language-section">
              <div className={styles.formLabel}>{t("trainer.preferences.language")}</div>
              <div style={{ marginTop: 8 }}>
                <HindiToggle />
              </div>
            </div>

            <div className={styles.formField}>
              <span className={styles.formLabel}>{t("trainer.preferences.font_size")}</span>
              <div className={styles.radioGroup} role="radiogroup" aria-label="font size">
                {FONT_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    type="button"
                    className={styles.radioOption}
                    data-checked={fontSize === opt.value ? "true" : "false"}
                    data-testid={opt.testId}
                    role="radio"
                    aria-checked={fontSize === opt.value}
                    onClick={() => {
                      setFontSize(opt.value);
                      persist({ font_size: opt.value });
                    }}
                  >
                    {t(opt.i18nKey)}
                  </button>
                ))}
              </div>
            </div>

            <div className={styles.toggleRow}>
              <div>
                <div className={styles.toggleLabel}>{t("trainer.preferences.low_data")}</div>
                <div className={styles.toggleDescription}>
                  {t("trainer.preferences.low_data_help")}
                </div>
              </div>
              <button
                type="button"
                className={styles.toggleSwitch}
                data-on={lowData ? "true" : "false"}
                data-testid="toggle-low-data"
                aria-pressed={lowData}
                aria-label={t("trainer.preferences.low_data")}
                onClick={() => {
                  const next = !lowData;
                  setLowData(next);
                  persist({ low_data: next });
                }}
              >
                <span className={styles.toggleKnob} />
              </button>
            </div>

            <div className={styles.toggleRow}>
              <div className={styles.toggleLabel}>{t("trainer.preferences.voice_default")}</div>
              <button
                type="button"
                className={styles.toggleSwitch}
                data-on={voiceDefault ? "true" : "false"}
                data-testid="toggle-voice-default"
                aria-pressed={voiceDefault}
                aria-label={t("trainer.preferences.voice_default")}
                onClick={() => {
                  const next = !voiceDefault;
                  setVoiceDefault(next);
                  persist({ voice_default: next });
                }}
              >
                <span className={styles.toggleKnob} />
              </button>
            </div>

            {savedFlash && (
              <div className={styles.savedNote} data-testid="preferences-saved-flash">
                {t("trainer.settings.saved")}
              </div>
            )}
          </div>
        )}
      </SettingsLayout>
    </RoleGate>
  );
};

PreferencesPage.title = "Preferences";
PreferencesPage.path = "/trainer/settings/preferences";
PreferencesPage.exact = true;

export default PreferencesPage;
