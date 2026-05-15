/**
 * Shared types for the TrainPlex Trainer Settings pages.
 * Mirrors the backend contract in `label_studio/users/api_profile.py::_serialize_profile`.
 * Phase 1 Step 13.
 */

export type Cadence = "daily" | "weekly" | "manual";
export type Tier = "bronze" | "silver" | "gold";
export type FontSize = "small" | "medium" | "large";

export interface PayoutSettings {
  upi_id: string;
  bank_account: string;
  cadence: Cadence;
  min_withdraw_inr: number;
}

export interface NotificationPrefs {
  wa: boolean;
  email: boolean;
  sms: boolean;
  push: boolean;
  quiet_hours: boolean;
  frequency_limit: boolean;
}

export interface ProfileStats {
  total_tasks: number;
  total_earnings_inr: number;
}

export interface TrainerProfile {
  id: number;
  email: string;
  first_name: string;
  last_name: string;
  phone: string;
  avatar_url: string | null;
  role: "trainer" | "reviewer" | "qa_lead" | "admin";
  date_joined: string | null;
  state: string;
  city: string;
  pincode: string;
  language: "en" | "hi" | string;
  tier: Tier;
  payout_settings: PayoutSettings;
  notification_prefs: NotificationPrefs;
  stats: ProfileStats;
}

export interface ActiveSession {
  id: string;
  created_at: string;
  ip_address: string;
  user_agent: string;
  is_current: boolean;
}

export interface LoginHistoryRow {
  id: number;
  action: "login_success" | "login_fail";
  success: boolean;
  ip_address: string | null;
  user_agent: string;
  created_at: string;
}
