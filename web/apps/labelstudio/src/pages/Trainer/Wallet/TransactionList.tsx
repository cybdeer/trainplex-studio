/**
 * TransactionList — recent 30 wallet transactions for the trainer.
 *
 * Phase 1 Step 6.4. Renders the `transactions` array from the wallet
 * response. Each row carries a coloured circular icon (founder palette):
 *   hold    → orange "H"
 *   release → green  "R"
 *   payout  → indigo "P"
 *   refund  → grey   "X"
 *
 * Description is i18n-keyed; the founder personal mobile must NEVER
 * appear here (the backend description string never contains it; the
 * frontend just renders what it received).
 */

import { useTranslation } from "@humansignal/app-common";
import type { WalletTxnRow, WalletTxnType } from "./types";
import styles from "./Wallet.module.css";

const ICON_CLASS: Record<WalletTxnType, string> = {
  hold: styles.txnIconHold,
  release: styles.txnIconRelease,
  payout: styles.txnIconPayout,
  refund: styles.txnIconRefund,
};

const AMOUNT_CLASS: Record<WalletTxnType, string> = {
  hold: styles.txnAmountHold,
  release: styles.txnAmountRelease,
  payout: styles.txnAmountPayout,
  refund: styles.txnAmountRefund,
};

const ICON_LETTER: Record<WalletTxnType, string> = {
  hold: "H",
  release: "R",
  payout: "P",
  refund: "X",
};

const I18N_LABEL_KEY: Record<WalletTxnType, string> = {
  hold: "trainer.wallet.txn_hold",
  release: "trainer.wallet.txn_release",
  payout: "trainer.wallet.txn_payout",
  refund: "trainer.wallet.txn_refund",
};

const SIGN: Record<WalletTxnType, string> = {
  hold: "",
  release: "+",
  payout: "−",
  refund: "",
};

function formatDateTime(iso: string): string {
  try {
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString();
  } catch {
    return iso;
  }
}

export interface TransactionListProps {
  transactions: WalletTxnRow[];
}

export function TransactionList({ transactions }: TransactionListProps) {
  const { t } = useTranslation();

  if (transactions.length === 0) {
    return (
      <div className={styles.emptyBox} data-testid="wallet-txn-empty">
        {t("trainer.wallet.no_transactions")}
      </div>
    );
  }

  return (
    <ul className={styles.txnList} data-testid="wallet-txn-list">
      {transactions.map((txn) => (
        <li
          key={txn.id}
          className={styles.txnRow}
          data-testid={`wallet-txn-row-${txn.id}`}
        >
          <span
            className={`${styles.txnIcon} ${ICON_CLASS[txn.txn_type]}`}
            data-testid={`wallet-txn-icon-${txn.id}`}
          >
            {ICON_LETTER[txn.txn_type]}
          </span>
          <span className={styles.txnDescription}>
            <span className={styles.txnLabel}>
              {t(I18N_LABEL_KEY[txn.txn_type])}
              {txn.related_task_id ? ` · #${txn.related_task_id}` : ""}
            </span>
            <span className={styles.txnTime}>{formatDateTime(txn.created_at)}</span>
          </span>
          <span style={{ textAlign: "right" }}>
            <span
              className={`${styles.txnAmount} ${AMOUNT_CLASS[txn.txn_type]}`}
              data-testid={`wallet-txn-amount-${txn.id}`}
            >
              {SIGN[txn.txn_type]}₹{txn.amount_inr}
            </span>
            <div className={styles.txnBalance}>
              ₹{txn.balance_after_inr}
            </div>
          </span>
        </li>
      ))}
    </ul>
  );
}
