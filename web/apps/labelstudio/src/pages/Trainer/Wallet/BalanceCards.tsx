/**
 * BalanceCards — 3 cards across the top of the trainer wallet.
 *
 * Phase 1 Step 6.4. Cards:
 *   - Available Balance (₹X) — money the trainer can withdraw.
 *   - Hold (3-reviewer wait) (₹X) — money frozen pending consensus.
 *   - This month earnings (₹X) — running sum of release rows.
 */

import { useTranslation } from "@humansignal/app-common";
import styles from "./Wallet.module.css";

export interface BalanceCardsProps {
  balanceInr: string;
  heldInr: string;
  thisMonthInr: string;
}

export function BalanceCards({
  balanceInr,
  heldInr,
  thisMonthInr,
}: BalanceCardsProps) {
  const { t } = useTranslation();
  return (
    <div className={styles.balanceCards} data-testid="wallet-balance-cards">
      <div className={styles.balanceCard} data-testid="wallet-balance-available">
        <span className={styles.balanceCardLabel}>
          {t("trainer.wallet.balance")}
        </span>
        <span className={styles.balanceCardAmount}>₹{balanceInr}</span>
      </div>
      <div
        className={`${styles.balanceCard} ${styles.balanceCardHeld}`}
        data-testid="wallet-balance-held"
      >
        <span className={styles.balanceCardLabel}>{t("trainer.wallet.held")}</span>
        <span className={styles.balanceCardAmount}>₹{heldInr}</span>
        <span className={styles.balanceCardHelper}>
          {t("trainer.wallet.held_hint")}
        </span>
      </div>
      <div
        className={`${styles.balanceCard} ${styles.balanceCardMonth}`}
        data-testid="wallet-balance-month"
      >
        <span className={styles.balanceCardLabel}>
          {t("trainer.wallet.this_month")}
        </span>
        <span className={styles.balanceCardAmount}>₹{thisMonthInr}</span>
      </div>
    </div>
  );
}
