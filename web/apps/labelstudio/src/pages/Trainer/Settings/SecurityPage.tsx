/**
 * SecurityPage — change password, 2FA link, active sessions, login
 * history, account deletion with cooldown.
 *
 * Phase 1 Step 13.
 *
 * 2FA link routes to /settings/2fa/enroll (Step 12.4 wire-in). Account
 * deletion in Phase 1 just shows the warning + button; backend cooldown
 * logic lands in Phase 2.
 */

import { RoleGate, Spinner } from "@humansignal/ui";
import { useTranslation } from "@humansignal/app-common";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { useAPI } from "../../../providers/ApiProvider";
import type { Page } from "../../types/Page";
import { SettingsLayout } from "./SettingsLayout";
import type { ActiveSession, LoginHistoryRow } from "./types";
import styles from "./Settings.module.css";

const SESSIONS_QUERY_KEY = "trainer-sessions";
const HISTORY_QUERY_KEY = "trainer-login-history";

export const SecurityPage: Page = () => {
  const api = useAPI();
  const { t } = useTranslation();
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const [pwForm, setPwForm] = useState({ old: "", new: "", confirm: "" });
  const [pwError, setPwError] = useState<string | null>(null);
  const [pwSuccess, setPwSuccess] = useState<string | null>(null);

  const { data: sessions } = useQuery<ActiveSession[]>({
    queryKey: [SESSIONS_QUERY_KEY],
    queryFn: async () => {
      const res = await api.callApi("trainerSessions");
      return (res as ActiveSession[]) ?? [];
    },
    enabled: user?.role === "trainer",
  });

  const { data: history } = useQuery<LoginHistoryRow[]>({
    queryKey: [HISTORY_QUERY_KEY],
    queryFn: async () => {
      const res = await api.callApi("trainerLoginHistory");
      return (res as LoginHistoryRow[]) ?? [];
    },
    enabled: user?.role === "trainer",
  });

  const changePassword = useMutation({
    mutationFn: async (payload: { old_password: string; new_password: string }) => {
      return api.callApi("trainerPasswordChange", { body: payload });
    },
    onSuccess: () => {
      setPwSuccess(t("trainer.security.password_changed"));
      setPwError(null);
      setPwForm({ old: "", new: "", confirm: "" });
    },
    onError: (err: unknown) => {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ??
        t("trainer.settings.save_failed");
      setPwError(msg);
      setPwSuccess(null);
    },
  });

  const revokeSession = useMutation({
    mutationFn: async (sessionId: string) => {
      return api.callApi("trainerSessionRevoke", { params: { session_id: sessionId } });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [SESSIONS_QUERY_KEY] });
    },
  });

  const onSubmitPassword = (e: React.FormEvent) => {
    e.preventDefault();
    if (pwForm.new !== pwForm.confirm) {
      setPwError(t("trainer.security.password_mismatch"));
      return;
    }
    changePassword.mutate({ old_password: pwForm.old, new_password: pwForm.new });
  };

  return (
    <RoleGate
      allow={["trainer"]}
      userRole={user?.role}
      fallback={
        <div className={styles.errorBox} data-testid="security-forbidden">
          403 — trainer only
        </div>
      }
    >
      <SettingsLayout>
        <h1 className={styles.pageTitle}>{t("trainer.settings.security")}</h1>

        {/* ---- Change password ---- */}
        <section data-testid="change-password-section" style={{ marginBottom: 32 }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>
            {t("trainer.security.change_password")}
          </h2>
          <form className={styles.formGrid} onSubmit={onSubmitPassword}>
            <div className={styles.formField}>
              <label htmlFor="old_password" className={styles.formLabel}>
                {t("trainer.security.old_password")}
              </label>
              <input
                id="old_password"
                type="password"
                className={styles.formInput}
                value={pwForm.old}
                onChange={(e) => setPwForm((f) => ({ ...f, old: e.target.value }))}
                data-testid="pw-old"
              />
            </div>
            <div className={styles.formField}>
              <label htmlFor="new_password" className={styles.formLabel}>
                {t("trainer.security.new_password")}
              </label>
              <input
                id="new_password"
                type="password"
                className={styles.formInput}
                value={pwForm.new}
                onChange={(e) => setPwForm((f) => ({ ...f, new: e.target.value }))}
                data-testid="pw-new"
              />
            </div>
            <div className={styles.formField}>
              <label htmlFor="confirm_password" className={styles.formLabel}>
                {t("trainer.security.confirm_password")}
              </label>
              <input
                id="confirm_password"
                type="password"
                className={styles.formInput}
                value={pwForm.confirm}
                onChange={(e) => setPwForm((f) => ({ ...f, confirm: e.target.value }))}
                data-testid="pw-confirm"
              />
            </div>
            <div className={styles.formActions}>
              <button
                type="submit"
                className="lsf-button lsf-button_look_filled lsf-button_size_medium"
                data-testid="pw-submit"
                disabled={changePassword.isPending}
              >
                {t("trainer.security.submit_change")}
              </button>
              {pwSuccess && (
                <span className={styles.savedNote} data-testid="pw-success">
                  {pwSuccess}
                </span>
              )}
              {pwError && (
                <span style={{ color: "#b91c1c", fontSize: 13 }} data-testid="pw-error">
                  {pwError}
                </span>
              )}
            </div>
          </form>
        </section>

        {/* ---- 2FA toggle / link ---- */}
        <section data-testid="two-factor-section" style={{ marginBottom: 32 }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>
            {t("trainer.security.two_factor")}
          </h2>
          <a
            href="/settings/2fa/enroll"
            className="lsf-button lsf-button_look_outlined lsf-button_size_small"
            data-testid="two-factor-enroll-link"
          >
            {t("trainer.security.two_factor_enroll")}
          </a>
        </section>

        {/* ---- Active sessions ---- */}
        <section data-testid="sessions-section" style={{ marginBottom: 32 }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>
            {t("trainer.security.active_sessions")}
          </h2>
          {!sessions ? (
            <Spinner />
          ) : (
            sessions.map((s) => (
              <div className={styles.sessionRow} key={s.id} data-testid={`session-row-${s.id}`}>
                <div>
                  <div style={{ fontWeight: 500 }}>{s.user_agent || "—"}</div>
                  <div style={{ fontSize: 12, color: "#6b7280" }}>
                    {s.ip_address || "?"} · {s.is_current ? t("trainer.security.current_session") : ""}
                  </div>
                </div>
                <button
                  type="button"
                  className="lsf-button lsf-button_look_outlined lsf-button_size_small"
                  onClick={() => revokeSession.mutate(s.id)}
                  data-testid={`session-revoke-${s.id}`}
                >
                  {t("trainer.security.revoke")}
                </button>
              </div>
            ))
          )}
        </section>

        {/* ---- Login history ---- */}
        <section data-testid="login-history-section" style={{ marginBottom: 32 }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>
            {t("trainer.security.login_history")}
          </h2>
          {!history ? (
            <Spinner />
          ) : history.length === 0 ? (
            <div style={{ fontSize: 13, color: "#6b7280" }}>—</div>
          ) : (
            history.map((row) => (
              <div className={styles.historyRow} key={row.id} data-testid={`history-row-${row.id}`}>
                <div>
                  <div style={{ fontWeight: 500 }}>
                    {row.action === "login_success" ? "✓" : "✗"} {row.action}
                  </div>
                  <div style={{ fontSize: 12, color: "#6b7280" }}>
                    {row.ip_address || "?"} · {row.user_agent}
                  </div>
                </div>
                <div style={{ fontSize: 12, color: "#6b7280" }}>{row.created_at}</div>
              </div>
            ))
          )}
        </section>

        {/* ---- Account deletion ---- */}
        <section data-testid="delete-account-section">
          <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 12 }}>
            {t("trainer.security.delete_account")}
          </h2>
          <div className={styles.deleteWarning}>
            {t("trainer.security.delete_account_warning")}
          </div>
          <button
            type="button"
            className="lsf-button lsf-button_look_danger lsf-button_size_small"
            data-testid="delete-account-btn"
          >
            {t("trainer.security.request_delete")}
          </button>
        </section>
      </SettingsLayout>
    </RoleGate>
  );
};

SecurityPage.title = "Security";
SecurityPage.path = "/trainer/settings/security";
SecurityPage.exact = true;

export default SecurityPage;
