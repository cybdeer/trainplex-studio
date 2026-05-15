/**
 * ProfilePage — trainer self-service profile editor.
 *
 * Per plan Step 13: avatar upload + display, editable name / phone /
 * address (state, city, pincode), tier badge (read-only), total tasks
 * + earnings stats.
 *
 * Role + email are read-only — the React form does not even render
 * them as editable, but even if the trainer crafts a PATCH against
 * the API directly the backend silently drops them.
 *
 * Phase 1 Step 13.
 */

import { RoleGate, Spinner } from "@humansignal/ui";
import { useTranslation } from "@humansignal/app-common";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { useAPI } from "../../../providers/ApiProvider";
import type { Page } from "../../types/Page";
import { SettingsLayout } from "./SettingsLayout";
import type { TrainerProfile } from "./types";
import styles from "./Settings.module.css";

const PROFILE_QUERY_KEY = "trainer-profile";

export const ProfilePage: Page = () => {
  const api = useAPI();
  const { t } = useTranslation();
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [savedFlash, setSavedFlash] = useState(false);

  const { data: profile, isFetching, isError } = useQuery<TrainerProfile>({
    queryKey: [PROFILE_QUERY_KEY],
    queryFn: async () => {
      const res = await api.callApi("trainerProfile");
      return res as TrainerProfile;
    },
    enabled: user?.role === "trainer",
  });

  // Local form state — initialised from the fetched profile.
  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    phone: "",
    state: "",
    city: "",
    pincode: "",
  });

  useEffect(() => {
    if (profile) {
      setForm({
        first_name: profile.first_name || "",
        last_name: profile.last_name || "",
        phone: profile.phone || "",
        state: profile.state || "",
        city: profile.city || "",
        pincode: profile.pincode || "",
      });
    }
  }, [profile]);

  const updateProfile = useMutation({
    mutationFn: async (payload: Partial<TrainerProfile>) => {
      return api.callApi("trainerProfileUpdate", { body: payload });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [PROFILE_QUERY_KEY] });
      setSavedFlash(true);
      setTimeout(() => setSavedFlash(false), 2000);
    },
  });

  const uploadAvatar = useMutation({
    mutationFn: async (file: File) => {
      const fd = new FormData();
      fd.append("avatar", file);
      return api.callApi("trainerProfileAvatar", { body: fd });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [PROFILE_QUERY_KEY] });
    },
  });

  const onChange = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement>) => {
    setForm((f) => ({ ...f, [k]: e.target.value }));
  };

  const onSave = (e: React.FormEvent) => {
    e.preventDefault();
    updateProfile.mutate(form);
  };

  const onAvatarPick = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) uploadAvatar.mutate(file);
  };

  return (
    <RoleGate
      allow={["trainer"]}
      userRole={user?.role}
      fallback={
        <div className={styles.errorBox} data-testid="profile-forbidden">
          403 — trainer only
        </div>
      }
    >
      <SettingsLayout>
        <h1 className={styles.pageTitle}>{t("trainer.settings.profile")}</h1>

        {isFetching && !profile ? (
          <div className={styles.loadingBox} data-testid="profile-loading">
            <Spinner />
          </div>
        ) : isError || !profile ? (
          <div className={styles.errorBox} data-testid="profile-error">
            {t("common.error")}
          </div>
        ) : (
          <form onSubmit={onSave} data-testid="profile-form">
            <div className={styles.avatarRow}>
              <div className={styles.avatarPreview} data-testid="avatar-preview">
                {profile.avatar_url ? (
                  <img src={profile.avatar_url} alt={t("trainer.profile.avatar")} />
                ) : (
                  <span aria-hidden="true">
                    {(profile.first_name?.[0] || profile.email?.[0] || "?").toUpperCase()}
                  </span>
                )}
              </div>
              <div>
                <div className={styles.formLabel}>{t("trainer.profile.avatar")}</div>
                <input
                  type="file"
                  accept="image/*"
                  ref={fileInputRef}
                  style={{ display: "none" }}
                  onChange={onAvatarPick}
                  data-testid="avatar-input"
                />
                <button
                  type="button"
                  className="lsf-button lsf-button_look_outlined lsf-button_size_small"
                  onClick={() => fileInputRef.current?.click()}
                  data-testid="avatar-upload-btn"
                >
                  {t("trainer.profile.upload_avatar")}
                </button>
                <div style={{ marginTop: 8 }}>
                  <span className={styles.tierBadgeReadonly} data-testid="profile-tier-badge">
                    {t("trainer.profile.tier_badge")}: {profile.tier}
                  </span>
                </div>
              </div>
            </div>

            <div className={styles.formGrid}>
              <div className={styles.formField}>
                <label className={styles.formLabel} htmlFor="first_name">
                  {t("trainer.profile.first_name")}
                </label>
                <input
                  id="first_name"
                  className={styles.formInput}
                  value={form.first_name}
                  onChange={onChange("first_name")}
                  data-testid="profile-first-name"
                />
              </div>
              <div className={styles.formField}>
                <label className={styles.formLabel} htmlFor="last_name">
                  {t("trainer.profile.last_name")}
                </label>
                <input
                  id="last_name"
                  className={styles.formInput}
                  value={form.last_name}
                  onChange={onChange("last_name")}
                  data-testid="profile-last-name"
                />
              </div>
              <div className={styles.formField}>
                <label className={styles.formLabel} htmlFor="phone">
                  {t("trainer.profile.phone")}
                </label>
                <input
                  id="phone"
                  className={styles.formInput}
                  value={form.phone}
                  onChange={onChange("phone")}
                  data-testid="profile-phone"
                />
              </div>
              <div className={styles.formField}>
                <label className={styles.formLabel} htmlFor="state">
                  {t("trainer.profile.state")}
                </label>
                <input
                  id="state"
                  className={styles.formInput}
                  value={form.state}
                  onChange={onChange("state")}
                  data-testid="profile-state"
                />
              </div>
              <div className={styles.formField}>
                <label className={styles.formLabel} htmlFor="city">
                  {t("trainer.profile.city")}
                </label>
                <input
                  id="city"
                  className={styles.formInput}
                  value={form.city}
                  onChange={onChange("city")}
                  data-testid="profile-city"
                />
              </div>
              <div className={styles.formField}>
                <label className={styles.formLabel} htmlFor="pincode">
                  {t("trainer.profile.pincode")}
                </label>
                <input
                  id="pincode"
                  className={styles.formInput}
                  value={form.pincode}
                  onChange={onChange("pincode")}
                  data-testid="profile-pincode"
                />
              </div>
            </div>

            <div className={styles.statsGrid} data-testid="profile-stats-grid">
              <div className={styles.statCard}>
                <div className={styles.statValue} data-testid="stat-total-tasks">
                  {profile.stats.total_tasks}
                </div>
                <div className={styles.statLabel}>{t("trainer.profile.stats_tasks")}</div>
              </div>
              <div className={styles.statCard}>
                <div className={styles.statValue} data-testid="stat-total-earnings">
                  ₹{profile.stats.total_earnings_inr}
                </div>
                <div className={styles.statLabel}>{t("trainer.profile.stats_earnings")}</div>
              </div>
            </div>

            <div className={styles.formActions}>
              <button
                type="submit"
                className="lsf-button lsf-button_look_filled lsf-button_size_medium"
                data-testid="profile-save-btn"
                disabled={updateProfile.isPending}
              >
                {t("trainer.profile.save")}
              </button>
              {savedFlash && (
                <span className={styles.savedNote} data-testid="profile-saved-flash">
                  {t("trainer.settings.saved")}
                </span>
              )}
            </div>
          </form>
        )}
      </SettingsLayout>
    </RoleGate>
  );
};

ProfilePage.title = "Profile";
ProfilePage.path = "/trainer/settings/profile";
ProfilePage.exact = true;

export default ProfilePage;
