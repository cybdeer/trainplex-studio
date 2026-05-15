/**
 * TwoFactorSetup — TrainPlex Phase 1 Step 12.4 wire-in.
 *
 * Three-step enrollment wizard for the admin / qa_lead 2FA flow:
 *
 *   A) Server returns a fresh secret + provisioning URI on /enroll/start.
 *      We render the secret in plain text (and the otpauth:// URI as a
 *      copyable string) so the user can either type it into their
 *      authenticator app or paste it into a separate QR-rendering tool.
 *      We deliberately DON'T pull in a QR-rendering JS library to keep
 *      bundle weight + dependency surface down — the secret + issuer
 *      are clearly displayed and most authenticator apps accept manual
 *      entry on the same screen.
 *
 *   B) User types the 6-digit code their app shows. We POST the secret
 *      back to /enroll/confirm; on 200 the backend persists totp_enabled
 *      and returns 10 fresh backup codes.
 *
 *   C) Display the 10 backup codes once with a copy-all + download
 *      action. User must click "I've saved them" to leave the screen.
 */

import { useCallback, useState } from "react";
import { Button, RoleGate, Typography } from "@humansignal/ui";
import { useTranslation } from "@humansignal/app-common";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { useAPI } from "../../../providers/ApiProvider";
import styles from "./TwoFactor.module.css";

type WizardStep = "start" | "verify" | "backup";

interface EnrollStartResponse {
  secret: string;
  provisioning_uri: string;
}

interface EnrollConfirmResponse {
  totp_enabled: boolean;
  backup_codes: string[];
}

export const TwoFactorSetup = () => {
  const api = useAPI();
  const { user } = useAuth();
  const { t } = useTranslation();

  const [step, setStep] = useState<WizardStep>("start");
  const [secret, setSecret] = useState<string>("");
  const [provisioningUri, setProvisioningUri] = useState<string>("");
  const [code, setCode] = useState<string>("");
  const [backupCodes, setBackupCodes] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleStart = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const res = (await api.callApi("twoFactorEnrollStart")) as EnrollStartResponse;
      if (!res || !res.secret) {
        // ApiProvider sets .error on the response when the request 4xx/5xx's;
        // fall through to a generic message rather than risking a stale state.
        setError(t("common.error"));
        return;
      }
      setSecret(res.secret);
      setProvisioningUri(res.provisioning_uri);
      setStep("verify");
    } catch (err) {
      setError(t("common.error"));
    } finally {
      setBusy(false);
    }
  }, [api, t]);

  const handleVerify = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const res = (await api.callApi("twoFactorEnrollConfirm", {
        body: { secret, token: code.trim() },
      })) as EnrollConfirmResponse;
      if (!res || !res.totp_enabled || !Array.isArray(res.backup_codes)) {
        setError(t("auth.invalid_credentials"));
        return;
      }
      setBackupCodes(res.backup_codes);
      setStep("backup");
    } catch (err) {
      setError(t("auth.invalid_credentials"));
    } finally {
      setBusy(false);
    }
  }, [api, code, secret, t]);

  const copyAllCodes = useCallback(() => {
    void navigator.clipboard?.writeText(backupCodes.join("\n"));
  }, [backupCodes]);

  const downloadCodes = useCallback(() => {
    const blob = new Blob([backupCodes.join("\n")], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "trainplex-2fa-backup-codes.txt";
    a.click();
    URL.revokeObjectURL(url);
  }, [backupCodes]);

  return (
    <RoleGate
      allow={["admin", "qa_lead"]}
      userRole={user?.role}
      fallback={
        <div className={styles.root} data-testid="twofa-forbidden">
          <Typography variant="body" size="medium">
            2FA is only available for admin and QA-lead roles.
          </Typography>
        </div>
      }
    >
      <main className={styles.root} data-testid="twofa-setup">
        <h1 className={styles.title}>{t("admin.2fa.setup_title")}</h1>

        <div className={styles.stepIndicator} aria-label="wizard steps">
          <span data-active={step === "start"}>1. Start</span>
          <span> · </span>
          <span data-active={step === "verify"}>2. Verify</span>
          <span> · </span>
          <span data-active={step === "backup"}>3. Backup codes</span>
        </div>

        {error && (
          <div className={styles.error} role="alert" data-testid="twofa-error">
            {error}
          </div>
        )}

        {step === "start" && (
          <>
            <Typography variant="body" size="medium" className={styles.subtitle}>
              Open your authenticator app (Google Authenticator, Authy, or similar) before clicking
              the button below. You'll see a code to scan or enter.
            </Typography>
            <div className={styles.actions}>
              <Button onClick={handleStart} waiting={busy} data-testid="twofa-start-btn">
                Start setup
              </Button>
            </div>
          </>
        )}

        {step === "verify" && (
          <>
            <Typography variant="body" size="medium">
              {t("admin.2fa.scan_qr")}
            </Typography>

            <div className={styles.qrFallback} data-testid="twofa-secret">
              <label htmlFor="twofa-secret-input">Secret (manual entry):</label>
              <code id="twofa-secret-input" className={styles.secret}>
                {secret}
              </code>
              <label htmlFor="twofa-uri-input">Or copy this otpauth URI into a QR generator:</label>
              <code id="twofa-uri-input" className={styles.provisioningUri}>
                {provisioningUri}
              </code>
            </div>

            <div className={styles.codeRow}>
              <label htmlFor="twofa-code-input">{t("admin.2fa.enter_code")}</label>
              <input
                id="twofa-code-input"
                className={styles.codeInput}
                type="text"
                inputMode="numeric"
                pattern="\d{6}"
                maxLength={6}
                autoComplete="one-time-code"
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))}
                data-testid="twofa-code-input"
              />
            </div>

            <div className={styles.actions}>
              <Button
                look="outlined"
                onClick={() => {
                  setStep("start");
                  setCode("");
                  setSecret("");
                  setProvisioningUri("");
                }}
                data-testid="twofa-back-btn"
              >
                {t("common.cancel")}
              </Button>
              <Button
                onClick={handleVerify}
                waiting={busy}
                disabled={code.length !== 6}
                data-testid="twofa-verify-btn"
              >
                {t("admin.2fa.verify")}
              </Button>
            </div>
          </>
        )}

        {step === "backup" && (
          <>
            <h2 className={styles.title} style={{ fontSize: "1rem" }}>
              {t("admin.2fa.backup_codes_title")}
            </h2>

            <div className={styles.warning} role="note" data-testid="twofa-warning">
              {t("admin.2fa.backup_codes_warning")}
            </div>

            <div className={styles.backupCodes} data-testid="twofa-backup-codes">
              {backupCodes.map((c) => (
                <code key={c} className={styles.backupCode}>
                  {c}
                </code>
              ))}
            </div>

            <div className={styles.actions}>
              <Button look="outlined" onClick={copyAllCodes} data-testid="twofa-copy-btn">
                Copy all
              </Button>
              <Button look="outlined" onClick={downloadCodes} data-testid="twofa-download-btn">
                Download .txt
              </Button>
              <Button
                onClick={() => window.location.assign("/projects")}
                data-testid="twofa-done-btn"
              >
                I've saved them
              </Button>
            </div>
          </>
        )}
      </main>
    </RoleGate>
  );
};

(TwoFactorSetup as any).title = "Two-factor setup";
(TwoFactorSetup as any).path = "/settings/2fa/enroll";
(TwoFactorSetup as any).exact = true;

export default TwoFactorSetup;
