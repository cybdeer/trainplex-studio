/**
 * TwoFactorDisable — turn 2FA off after re-verifying password + current code.
 *
 * Phase 1 Step 12.4. Mounted at ``/settings/2fa/disable``. RoleGate +
 * server-side ``_gate_2fa_roles`` both restrict to admin + qa_lead.
 */

import { useCallback, useState } from "react";
import { Button, RoleGate, Typography } from "@humansignal/ui";
import { useTranslation } from "@humansignal/app-common";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { useAPI } from "../../../providers/ApiProvider";
import styles from "./TwoFactor.module.css";

interface DisableResponse {
  totp_enabled: boolean;
}

export const TwoFactorDisable = () => {
  const api = useAPI();
  const { user } = useAuth();
  const { t } = useTranslation();

  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const submit = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const res = (await api.callApi("twoFactorDisable", {
        body: { password, token: code.trim() },
      })) as DisableResponse;
      if (!res || res.totp_enabled !== false) {
        setError(t("auth.invalid_credentials"));
        return;
      }
      setSuccess(true);
    } catch (err) {
      setError(t("auth.invalid_credentials"));
    } finally {
      setBusy(false);
    }
  }, [api, password, code, t]);

  return (
    <RoleGate
      allow={["admin", "qa_lead"]}
      userRole={user?.role}
      fallback={
        <div className={styles.root} data-testid="twofa-disable-forbidden">
          <Typography variant="body" size="medium">
            2FA is only available for admin and QA-lead roles.
          </Typography>
        </div>
      }
    >
      <main className={styles.root} data-testid="twofa-disable">
        <h1 className={styles.title}>{t("admin.2fa.disable_title")}</h1>

        <div className={styles.warning} role="note">
          {t("admin.2fa.disable_warning")}
        </div>

        {error && (
          <div className={styles.error} role="alert" data-testid="twofa-disable-error">
            {error}
          </div>
        )}

        {success ? (
          <Typography variant="body" size="medium" data-testid="twofa-disable-success">
            2FA disabled. You can re-enroll at any time from the 2FA setup page.
          </Typography>
        ) : (
          <>
            <div className={styles.codeRow}>
              <label htmlFor="twofa-disable-password">Current password</label>
              <input
                id="twofa-disable-password"
                className={styles.codeInput}
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                data-testid="twofa-disable-password-input"
              />
            </div>

            <div className={styles.codeRow}>
              <label htmlFor="twofa-disable-code">{t("admin.2fa.enter_code")}</label>
              <input
                id="twofa-disable-code"
                className={styles.codeInput}
                type="text"
                inputMode="numeric"
                pattern="\d{6}"
                maxLength={6}
                autoComplete="one-time-code"
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                data-testid="twofa-disable-code-input"
              />
            </div>

            <div className={styles.actions}>
              <Button
                variant="negative"
                onClick={submit}
                waiting={busy}
                disabled={!password || code.length !== 6}
                data-testid="twofa-disable-submit"
              >
                Disable 2FA
              </Button>
            </div>
          </>
        )}
      </main>
    </RoleGate>
  );
};

(TwoFactorDisable as any).title = "Disable 2FA";
(TwoFactorDisable as any).path = "/settings/2fa/disable";
(TwoFactorDisable as any).exact = true;

export default TwoFactorDisable;
