/**
 * WalletPage — TrainPlex Trainer wallet view.
 *
 * Phase 1 Step 6.4. Surfaces:
 *   - Available balance (₹X) — money the trainer can withdraw.
 *   - Held balance (₹X) — frozen pending consensus.
 *   - This-month earnings (₹X) — released-to-wallet sum since 1st.
 *   - Recent 30 wallet transactions.
 *   - Link to /trainer/settings/payout for UPI / cadence setup.
 *
 * Backend
 * -------
 *   GET /api/v1/payments/wallet (trainer-only, self).
 *
 * Endpoint is `@require_role(['trainer'])`; we additionally wrap with
 * <RoleGate allow={['trainer']}> so a misrouted admin / reviewer sees
 * the 403 surface.
 */

import { RoleGate, Spinner } from "@humansignal/ui";
import { useTranslation } from "@humansignal/app-common";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@humansignal/core/providers/AuthProvider";
import { useAPI } from "../../../providers/ApiProvider";
import type { Page } from "../../types/Page";
import { BalanceCards } from "./BalanceCards";
import { TransactionList } from "./TransactionList";
import { WalletPayoutSettings } from "./WalletPayoutSettings";
import type { WalletResponse } from "./types";
import styles from "./Wallet.module.css";

const WALLET_QUERY_KEY = ["trainer-wallet"];

export const WalletPage: Page = () => {
  const api = useAPI();
  const { t } = useTranslation();
  const { user } = useAuth();

  const { data, isFetching, isError, refetch } = useQuery<WalletResponse>({
    queryKey: WALLET_QUERY_KEY,
    queryFn: async () => {
      const res = await api.callApi("trainerWallet");
      return res as WalletResponse;
    },
    staleTime: 30_000,
    enabled: user?.role === "trainer",
  });

  return (
    <main className={styles.walletRoot} data-testid="trainer-wallet-page">
      <RoleGate
        allow={["trainer"]}
        userRole={user?.role}
        fallback={
          <div className={styles.errorBox} data-testid="wallet-forbidden">
            403 — trainer only
          </div>
        }
      >
        <h1 className={styles.walletTitle}>{t("trainer.wallet.title")}</h1>

        {isFetching && !data ? (
          <div className={styles.loadingBox} data-testid="wallet-loading">
            <Spinner />
            <span style={{ marginLeft: 10 }}>{t("trainer.wallet.loading")}</span>
          </div>
        ) : isError || !data ? (
          <div className={styles.errorBox} data-testid="wallet-error">
            {t("trainer.wallet.load_failed")}
            <button
              type="button"
              className={styles.payoutSettingsLink}
              style={{ marginLeft: 8 }}
              onClick={() => refetch()}
            >
              {t("common.retry")}
            </button>
          </div>
        ) : (
          <>
            <BalanceCards
              balanceInr={data.balance_inr}
              heldInr={data.held_inr}
              thisMonthInr={data.this_month_inr}
            />
            <WalletPayoutSettings />
            <section className={styles.txnCard} data-testid="wallet-txn-card">
              <div className={styles.txnCardHeader}>
                <h2 className={styles.txnCardTitle}>
                  {t("trainer.wallet.recent_txn")}
                </h2>
                <span className={styles.txnNextPayout}>
                  {t("trainer.wallet.txn_count", {
                    count: data.transactions.length,
                  })}
                </span>
              </div>
              <TransactionList transactions={data.transactions} />
            </section>
          </>
        )}
      </RoleGate>
    </main>
  );
};

WalletPage.title = "My Wallet";
WalletPage.path = "/trainer/wallet";
WalletPage.exact = true;

export default WalletPage;
