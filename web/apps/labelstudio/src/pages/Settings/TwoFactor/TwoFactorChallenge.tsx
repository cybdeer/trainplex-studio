/**
 * TwoFactorChallenge — login second step.
 *
 * Phase 1 Step 12.4. After the password POST succeeds for a 2FA-enrolled
 * admin, the backend returns ``{requires_2fa: true, partial_token, persist_session}``.
 * This page collects the 6-digit code (or a backup code), POSTs to
 * ``/user/login/2fa``, and on success follows ``redirect_url`` into the
 * authenticated app.
 *
 * The partial_token lives in component state — we deliberately don't drop
 * it in localStorage / sessionStorage so a page refresh sends the user
 * back to the password step. That's the safer default for a 5-minute
 * single-use token.
 */

import { useCallback, useState } from "react";
import { Button } from "@humansignal/ui";
import { useTranslation } from "@humansignal/app-common";
import styles from "./TwoFactor.module.css";

export interface TwoFactorChallengeProps {
  /** Signed token returned by the password step. */
  partialToken: string;
  /** ``persist_session`` preference from the password form. */
  persistSession?: boolean;
  /** Called on success with the backend-resolved redirect URL. */
  onSuccess?: (redirectUrl: string) => void;
  /** Called when the user wants to bail and restart at the password step. */
  onCancel?: () => void;
}

interface VerifyResponse {
  success?: boolean;
  redirect_url?: string;
  detail?: string;
}

export const TwoFactorChallenge = ({
  partialToken,
  persistSession = false,
  onSuccess,
  onCancel,
}: TwoFactorChallengeProps) => {
  const { t } = useTranslation();
  const [mode, setMode] = useState<"totp" | "backup">("totp");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      // Use raw fetch — this endpoint isn't behind the LS API gateway
      // ApiProvider expects; it sits at /user/login/2fa next to the
      // password POST and accepts JSON body.
      const res = await fetch("/user/login/2fa", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "include",
        body: JSON.stringify({
          partial_token: partialToken,
          persist_session: persistSession,
          ...(mode === "totp" ? { token: code.trim() } : { backup_code: code.trim() }),
        }),
      });
      const body: VerifyResponse = await res.json().catch(() => ({}));
      if (!res.ok || !body.success) {
        setError(t("auth.invalid_credentials"));
        return;
      }
      const redirect = body.redirect_url || "/projects";
      if (onSuccess) {
        onSuccess(redirect);
      } else {
        window.location.assign(redirect);
      }
    } catch (err) {
      setError(t("common.error"));
    } finally {
      setBusy(false);
    }
  }, [code, mode, onSuccess, partialToken, persistSession, t]);

  const codeLength = mode === "totp" ? 6 : 8;
  const codeReady = mode === "totp" ? code.length === 6 : code.trim().length >= codeLength;

  return (
    <main className={styles.root} data-testid="twofa-challenge">
      <h1 className={styles.title}>{t("admin.2fa.challenge_title")}</h1>

      {error && (
        <div className={styles.error} role="alert" data-testid="twofa-challenge-error">
          {error}
        </div>
      )}

      <div className={styles.codeRow}>
        <label htmlFor="twofa-challenge-input">
          {mode === "totp" ? t("admin.2fa.enter_code") : "Enter a backup code"}
        </label>
        <input
          id="twofa-challenge-input"
          className={styles.codeInput}
          type="text"
          inputMode={mode === "totp" ? "numeric" : "text"}
          pattern={mode === "totp" ? "\\d{6}" : undefined}
          maxLength={mode === "totp" ? 6 : 32}
          autoComplete="one-time-code"
          autoFocus
          value={code}
          onChange={(e) => {
            const next = e.target.value;
            setCode(mode === "totp" ? next.replace(/\D/g, "").slice(0, 6) : next);
          }}
          data-testid="twofa-challenge-input"
        />
      </div>

      <div className={styles.actions}>
        {onCancel && (
          <Button look="outlined" onClick={onCancel} data-testid="twofa-challenge-cancel">
            {t("common.cancel")}
          </Button>
        )}
        <Button
          onClick={submit}
          waiting={busy}
          disabled={!codeReady}
          data-testid="twofa-challenge-submit"
        >
          {t("admin.2fa.verify")}
        </Button>
      </div>

      <button
        type="button"
        className={styles.linkButton}
        onClick={() => {
          setMode((m) => (m === "totp" ? "backup" : "totp"));
          setCode("");
          setError(null);
        }}
        data-testid="twofa-toggle-mode"
      >
        {mode === "totp" ? t("admin.2fa.use_backup") : t("admin.2fa.enter_code")}
      </button>
    </main>
  );
};

(TwoFactorChallenge as any).title = "Two-factor challenge";
(TwoFactorChallenge as any).path = "/user/login/2fa";
(TwoFactorChallenge as any).exact = true;

export default TwoFactorChallenge;
