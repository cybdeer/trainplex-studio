/**
 * Barrel for the TrainPlex Trainer surfaces.
 *
 * Phase 1 contents:
 * - Step 1.4-E (Batch view): /trainer/batch
 * - Step 13 (Settings):
 *     /trainer/settings/profile
 *     /trainer/settings/security
 *     /trainer/settings/notifications
 *     /trainer/settings/payout
 *     /trainer/settings/preferences
 * - Step 6.4 (Wallet): /trainer/wallet
 */

export { BatchPage } from "./Batch";
export {
  ProfilePage,
  SecurityPage,
  NotificationsPage,
  PayoutPage,
  PreferencesPage,
} from "./Settings";
export { WalletPage } from "./Wallet";
