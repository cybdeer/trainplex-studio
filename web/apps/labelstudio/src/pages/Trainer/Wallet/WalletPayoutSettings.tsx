/**
 * WalletPayoutSettings — link to the trainer payout settings page.
 *
 * Phase 1 Step 6.4. Cross-references Step 13 PayoutPage at
 * /trainer/settings/payout where the UPI ID + cadence live. We render
 * a callout here so the trainer can jump from wallet → payout config
 * without hunting in the sidebar.
 */

import { Link } from "react-router-dom";
import { useTranslation } from "@humansignal/app-common";
import styles from "./Wallet.module.css";

export function WalletPayoutSettings() {
  const { t } = useTranslation();
  return (
    <div className={styles.payoutSettings} data-testid="wallet-payout-settings">
      <div className={styles.payoutSettingsText}>
        <span className={styles.payoutSettingsTitle}>
          {t("trainer.wallet.payout_settings_title")}
        </span>
        <span className={styles.payoutSettingsHint}>
          {t("trainer.wallet.payout_settings_hint")}
        </span>
      </div>
      <Link
        to="/trainer/settings/payout"
        className={styles.payoutSettingsLink}
        data-testid="wallet-payout-settings-link"
      >
        {t("trainer.wallet.payout_settings_cta")}
      </Link>
    </div>
  );
}
