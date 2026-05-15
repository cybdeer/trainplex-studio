/**
 * PayoutPage — UPI / bank account, auto-payout cadence, minimum
 * withdrawal threshold, annual tax statement (placeholder).
 *
 * Phase 1 Step 13 — no real payout wiring. The form just persists the
 * trainer's preferences via the profile API. Phase 2 wires Cashfree /
 * Razorpay payouts.
 */

import { RoleGate, Spinner } from "@humansignal/ui";
import { useTranslation } from "@humansignal/app-common";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { useAPI } from "../../../providers/ApiProvider";
import type { Page } from "../../types/Page";
import { SettingsLayout } from "./SettingsLayout";
import type { Cadence, PayoutSettings, TrainerProfile } from "./types";
import styles from "./Settings.module.css";

const PROFILE_QUERY_KEY = "trainer-profile";

const CADENCES: Array<{ value: Cadence; i18nKey: string; testId: string }> = [
  { value: "daily", i18nKey: "trainer.payout.daily", testId: "cadence-daily" },
  { value: "weekly", i18nKey: "trainer.payout.weekly", testId: "cadence-weekly" },
  { value: "manual", i18nKey: "trainer.payout.manual", testId: "cadence-manual" },
];

export const PayoutPage: Page = () => {
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

  const [form, setForm] = useState<PayoutSettings>({
    upi_id: "",
    bank_account: "",
    cadence: "weekly",
    min_withdraw_inr: 100,
  });

  useEffect(() => {
    if (profile?.payout_settings) setForm(profile.payout_settings);
  }, [profile]);

  const save = useMutation({
    mutationFn: async (next: PayoutSettings) => {
      return api.callApi("trainerProfileUpdate", {
        body: { payout_settings: next },
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [PROFILE_QUERY_KEY] });
      setSavedFlash(true);
      setTimeout(() => setSavedFlash(false), 1500);
    },
  });

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    save.mutate(form);
  };

  return (
    <RoleGate
      allow={["trainer"]}
      userRole={user?.role}
      fallback={
        <div className={styles.errorBox} data-testid="payout-forbidden">
          403 — trainer only
        </div>
      }
    >
      <SettingsLayout>
        <h1 className={styles.pageTitle}>{t("trainer.settings.payout")}</h1>

        {isFetching && !profile ? (
          <div className={styles.loadingBox} data-testid="payout-loading">
            <Spinner />
          </div>
        ) : isError ? (
          <div className={styles.errorBox}>{t("common.error")}</div>
        ) : (
          <form className={styles.formGrid} onSubmit={onSubmit} data-testid="payout-form">
            <div className={styles.formField}>
              <label htmlFor="upi_id" className={styles.formLabel}>
                {t("trainer.payout.upi_id")}
              </label>
              <input
                id="upi_id"
                className={styles.formInput}
                placeholder={t("trainer.payout.upi_placeholder")}
                value={form.upi_id}
                onChange={(e) => setForm((f) => ({ ...f, upi_id: e.target.value }))}
                data-testid="payout-upi"
              />
            </div>
            <div className={styles.formField}>
              <label htmlFor="bank_account" className={styles.formLabel}>
                {t("trainer.payout.bank_account")}
              </label>
              <input
                id="bank_account"
                className={styles.formInput}
                placeholder={t("trainer.payout.bank_placeholder")}
                value={form.bank_account}
                onChange={(e) => setForm((f) => ({ ...f, bank_account: e.target.value }))}
                data-testid="payout-bank"
              />
            </div>
            <div className={styles.formField}>
              <span className={styles.formLabel}>{t("trainer.payout.cadence")}</span>
              <div className={styles.radioGroup} role="radiogroup" aria-label="payout cadence">
                {CADENCES.map((c) => (
                  <button
                    key={c.value}
                    type="button"
                    className={styles.radioOption}
                    data-checked={form.cadence === c.value ? "true" : "false"}
                    data-testid={c.testId}
                    role="radio"
                    aria-checked={form.cadence === c.value}
                    onClick={() => setForm((f) => ({ ...f, cadence: c.value }))}
                  >
                    {t(c.i18nKey)}
                  </button>
                ))}
              </div>
            </div>
            <div className={styles.formField}>
              <label htmlFor="min_withdraw" className={styles.formLabel}>
                {t("trainer.payout.min_withdraw")}
              </label>
              <input
                id="min_withdraw"
                type="number"
                min={0}
                className={styles.formInput}
                value={form.min_withdraw_inr}
                onChange={(e) =>
                  setForm((f) => ({
                    ...f,
                    min_withdraw_inr: Math.max(0, Number(e.target.value) || 0),
                  }))
                }
                data-testid="payout-min-withdraw"
              />
            </div>

            <div className={styles.formField}>
              <span className={styles.formLabel}>{t("trainer.payout.tax_statement")}</span>
              <button
                type="button"
                className="lsf-button lsf-button_look_outlined lsf-button_size_small"
                disabled
                data-testid="payout-tax-statement-btn"
                title={t("trainer.payout.tax_statement_unavailable")}
              >
                {t("trainer.payout.tax_statement_download")}
              </button>
            </div>

            <div className={styles.formActions}>
              <button
                type="submit"
                className="lsf-button lsf-button_look_filled lsf-button_size_medium"
                data-testid="payout-save-btn"
                disabled={save.isPending}
              >
                {t("trainer.profile.save")}
              </button>
              {savedFlash && (
                <span className={styles.savedNote} data-testid="payout-saved-flash">
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

PayoutPage.title = "Payout";
PayoutPage.path = "/trainer/settings/payout";
PayoutPage.exact = true;

export default PayoutPage;
