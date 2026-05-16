/**
 * Tests for the TrainPlex Trainer Wallet page.
 * Phase 1 Step 6.4.
 *
 * Strategy
 * --------
 * Same module-mock approach as PaymentStatusPage / BatchPage: mock
 * useAuth, useAPI, useTranslation, useQuery, react-router-dom at the
 * module-graph level so the page renders deterministically.
 *
 * Coverage
 * --------
 * - Page renders for trainer with mock response (balance + 3 txns).
 * - Each txn row carries the right icon class (hold/release/payout/refund).
 * - Non-trainer role sees the 403 surface.
 * - Loading state renders skeleton.
 * - Error state renders error box.
 * - Empty transactions renders the empty-state.
 * - Founder personal mobile NEVER appears in any rendered description.
 * - Hindi mode renders the Devanagari title.
 */

/* eslint-disable @typescript-eslint/no-var-requires */

import "@testing-library/jest-dom";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

// ---- Module mocks (must come before importing the SUT) ----

jest.mock("../../../../providers/ApiProvider", () => ({
  useAPI: () => ({ callApi: jest.fn() }),
  ApiContext: { Provider: ({ children }: any) => children },
}));

let mockUserRole: string | null = "trainer";
const setMockRole = (role: string | null) => {
  mockUserRole = role;
};
jest.mock("@humansignal/core/providers/AuthProvider", () => ({
  useAuth: () => ({ user: { role: mockUserRole } }),
}));

let mockQueryState: any = { data: undefined, isFetching: true, isError: false };
const setMockQuery = (state: any) => {
  mockQueryState = state;
};
jest.mock("@tanstack/react-query", () => ({
  useQuery: () => mockQueryState,
}));

let mockLang = "en";
let mockTranslations: Record<string, string> = {};
const setMockLang = (lang: string) => {
  mockLang = lang;
};
const setMockTranslations = (table: Record<string, string>) => {
  mockTranslations = table;
};
jest.mock("@humansignal/app-common", () => ({
  useTranslation: () => ({
    t: (key: string, vars?: Record<string, unknown>) => {
      const tpl = mockTranslations[key] ?? key;
      if (!vars) return tpl;
      return tpl.replace(/\{\{(\w+)\}\}/g, (_, name) => String(vars[name] ?? ""));
    },
    i18n: { language: mockLang },
  }),
}));

// ---- Now import the SUT ----

import { WalletPage } from "../WalletPage";
import { TransactionList } from "../TransactionList";
import { BalanceCards } from "../BalanceCards";
import type { WalletResponse, WalletTxnRow } from "../types";

// The founder mobile literal MUST NOT live in this source tree. The digits
// come from the ``TRAINPLEX_FOUNDER_MOBILE_GUARD`` env var, surfaced to the
// test runner via ``process.env`` (or jsdom's process.env when running under
// vitest / jest). When the env var is unset the variants list is empty and
// the leak-guard assertions short-circuit — see callers below.
const _RAW_GUARD =
  (typeof process !== "undefined" &&
    process.env &&
    (process.env.VITE_FOUNDER_MOBILE_GUARD ||
      process.env.TRAINPLEX_FOUNDER_MOBILE_GUARD)) ||
  "";
const _DIGITS_ONLY = _RAW_GUARD.replace(/\D+/g, "");
const _NO_CC = _DIGITS_ONLY.length === 12 && _DIGITS_ONLY.startsWith("91")
  ? _DIGITS_ONLY.slice(2)
  : _DIGITS_ONLY;
const FOUNDER_MOBILE = _NO_CC ? `+91${_NO_CC}` : "";
const FOUNDER_MOBILE_VARIANTS: string[] = _NO_CC
  ? [
      `+91${_NO_CC}`,
      `91${_NO_CC}`,
      _NO_CC,
      `+91 ${_NO_CC}`,
      `+91-${_NO_CC}`,
    ]
  : [];

const TXN_HOLD: WalletTxnRow = {
  id: 1,
  txn_type: "hold",
  amount_inr: "100.00",
  balance_after_inr: "0.00",
  description: "Task #501 held for review",
  related_task_id: 501,
  related_payout_id: null,
  created_at: "2026-05-15T12:00:00Z",
};

const TXN_RELEASE: WalletTxnRow = {
  id: 2,
  txn_type: "release",
  amount_inr: "100.00",
  balance_after_inr: "100.00",
  description: "Task #501 released to wallet",
  related_task_id: 501,
  related_payout_id: null,
  created_at: "2026-05-15T13:00:00Z",
};

const TXN_PAYOUT: WalletTxnRow = {
  id: 3,
  txn_type: "payout",
  amount_inr: "100.00",
  balance_after_inr: "0.00",
  description: "Task payout #21",
  related_task_id: null,
  related_payout_id: 21,
  created_at: "2026-05-15T14:00:00Z",
};

const TXN_REFUND: WalletTxnRow = {
  id: 4,
  txn_type: "refund",
  amount_inr: "50.00",
  balance_after_inr: "0.00",
  description: "Task #502 rejected — no payout",
  related_task_id: 502,
  related_payout_id: null,
  created_at: "2026-05-15T15:00:00Z",
};

const RESPONSE: WalletResponse = {
  balance_inr: "100.00",
  held_inr: "50.00",
  this_month_inr: "300.00",
  transactions: [TXN_HOLD, TXN_RELEASE, TXN_PAYOUT, TXN_REFUND],
  transaction_limit: 30,
};

function renderPage() {
  return render(
    <MemoryRouter>
      <WalletPage />
    </MemoryRouter>,
  );
}

describe("WalletPage", () => {
  beforeEach(() => {
    setMockRole("trainer");
    setMockTranslations({
      "trainer.wallet.title": "My Wallet",
      "trainer.wallet.balance": "Available Balance",
      "trainer.wallet.held": "Hold (3-reviewer wait)",
      "trainer.wallet.held_hint": "Released when 2+/3 reviewers agree.",
      "trainer.wallet.this_month": "This month earnings",
      "trainer.wallet.recent_txn": "Recent transactions",
      "trainer.wallet.txn_hold": "Held for review",
      "trainer.wallet.txn_release": "Released to wallet",
      "trainer.wallet.txn_payout": "Sent to UPI",
      "trainer.wallet.txn_refund": "Refunded",
      "trainer.wallet.no_transactions": "No transactions yet.",
      "trainer.wallet.loading": "Loading wallet…",
      "trainer.wallet.load_failed": "Couldn't load wallet.",
      "trainer.wallet.payout_settings_title": "Payout settings",
      "trainer.wallet.payout_settings_hint": "Configure UPI ID + cadence.",
      "trainer.wallet.payout_settings_cta": "Settings",
      "trainer.wallet.txn_count": "{{count}} entries",
      "common.retry": "Retry",
    });
  });

  it("renders for trainer with balance cards + transactions", () => {
    setMockRole("trainer");
    setMockQuery({ data: RESPONSE, isFetching: false, isError: false });
    renderPage();
    expect(screen.getByTestId("trainer-wallet-page")).toBeInTheDocument();
    expect(screen.getByTestId("wallet-balance-cards")).toBeInTheDocument();
    expect(screen.getByTestId("wallet-balance-available")).toHaveTextContent("100.00");
    expect(screen.getByTestId("wallet-balance-held")).toHaveTextContent("50.00");
    expect(screen.getByTestId("wallet-balance-month")).toHaveTextContent("300.00");
    expect(screen.getByTestId("wallet-txn-list")).toBeInTheDocument();
    // 4 rows.
    expect(screen.getByTestId("wallet-txn-row-1")).toBeInTheDocument();
    expect(screen.getByTestId("wallet-txn-row-2")).toBeInTheDocument();
    expect(screen.getByTestId("wallet-txn-row-3")).toBeInTheDocument();
    expect(screen.getByTestId("wallet-txn-row-4")).toBeInTheDocument();
  });

  it("renders correct icon letter per txn type", () => {
    setMockRole("trainer");
    setMockQuery({ data: RESPONSE, isFetching: false, isError: false });
    renderPage();
    expect(screen.getByTestId("wallet-txn-icon-1").textContent).toBe("H"); // hold
    expect(screen.getByTestId("wallet-txn-icon-2").textContent).toBe("R"); // release
    expect(screen.getByTestId("wallet-txn-icon-3").textContent).toBe("P"); // payout
    expect(screen.getByTestId("wallet-txn-icon-4").textContent).toBe("X"); // refund
  });

  it("shows 403 surface for non-trainer", () => {
    setMockRole("admin");
    setMockQuery({ data: undefined, isFetching: false, isError: false });
    renderPage();
    expect(screen.getByTestId("wallet-forbidden")).toBeInTheDocument();
  });

  it("renders loading skeleton before first response", () => {
    setMockRole("trainer");
    setMockQuery({ data: undefined, isFetching: true, isError: false });
    renderPage();
    expect(screen.getByTestId("wallet-loading")).toBeInTheDocument();
  });

  it("renders error box on query failure", () => {
    setMockRole("trainer");
    setMockQuery({ data: undefined, isFetching: false, isError: true });
    renderPage();
    expect(screen.getByTestId("wallet-error")).toBeInTheDocument();
  });

  it("renders empty transactions state", () => {
    setMockRole("trainer");
    setMockQuery({
      data: { ...RESPONSE, transactions: [] },
      isFetching: false,
      isError: false,
    });
    renderPage();
    expect(screen.getByTestId("wallet-txn-empty")).toBeInTheDocument();
  });

  it("renders payout-settings cross-link to /trainer/settings/payout", () => {
    setMockRole("trainer");
    setMockQuery({ data: RESPONSE, isFetching: false, isError: false });
    renderPage();
    const link = screen.getByTestId("wallet-payout-settings-link");
    expect(link).toBeInTheDocument();
    expect(link.getAttribute("href")).toBe("/trainer/settings/payout");
  });

  it("renders Hindi title under hi locale", () => {
    setMockRole("trainer");
    setMockLang("hi");
    setMockTranslations({
      "trainer.wallet.title": "मेरा वॉलेट",
      "trainer.wallet.balance": "उपलब्ध बैलेंस",
      "trainer.wallet.held": "Hold (3 रिव्यूअर के बाद)",
      "trainer.wallet.held_hint": "2+/3 रिव्यूअर के बाद release होगा।",
      "trainer.wallet.this_month": "इस महीने की कमाई",
      "trainer.wallet.recent_txn": "हाल के लेनदेन",
      "trainer.wallet.txn_hold": "Review के लिए hold",
      "trainer.wallet.txn_release": "वॉलेट में release",
      "trainer.wallet.txn_payout": "UPI को भेजा",
      "trainer.wallet.txn_refund": "Refund हुआ",
      "trainer.wallet.no_transactions": "अभी कोई लेनदेन नहीं।",
      "trainer.wallet.loading": "वॉलेट लोड हो रहा…",
      "trainer.wallet.load_failed": "वॉलेट लोड नहीं हुआ।",
      "trainer.wallet.payout_settings_title": "Payout settings",
      "trainer.wallet.payout_settings_hint": "UPI + cadence सेट करें।",
      "trainer.wallet.payout_settings_cta": "Settings",
      "trainer.wallet.txn_count": "{{count}} entries",
      "common.retry": "फिर कोशिश",
    });
    setMockQuery({ data: RESPONSE, isFetching: false, isError: false });
    renderPage();
    expect(screen.getByText("मेरा वॉलेट")).toBeInTheDocument();
  });

  it("does NOT leak founder personal mobile into any rendered text", () => {
    setMockRole("trainer");
    setMockQuery({ data: RESPONSE, isFetching: false, isError: false });
    const { container } = renderPage();
    const html = container.innerHTML;
    for (const variant of FOUNDER_MOBILE_VARIANTS) {
      const normalised = html.replace(/\s|-/g, "");
      const needle = variant.replace(/\s|-/g, "");
      expect(normalised.includes(needle)).toBe(false);
    }
  });
});

describe("TransactionList", () => {
  beforeEach(() => {
    setMockTranslations({
      "trainer.wallet.txn_hold": "Held for review",
      "trainer.wallet.txn_release": "Released to wallet",
      "trainer.wallet.txn_payout": "Sent to UPI",
      "trainer.wallet.txn_refund": "Refunded",
      "trainer.wallet.no_transactions": "No transactions yet.",
    });
  });

  it("renders empty state for empty array", () => {
    render(<TransactionList transactions={[]} />);
    expect(screen.getByTestId("wallet-txn-empty")).toBeInTheDocument();
  });

  it("renders 4 rows with mixed txn types", () => {
    render(
      <TransactionList transactions={[TXN_HOLD, TXN_RELEASE, TXN_PAYOUT, TXN_REFUND]} />,
    );
    expect(screen.getAllByTestId(/wallet-txn-row-/)).toHaveLength(4);
  });
});

describe("BalanceCards", () => {
  beforeEach(() => {
    setMockTranslations({
      "trainer.wallet.balance": "Available Balance",
      "trainer.wallet.held": "Hold (3-reviewer wait)",
      "trainer.wallet.held_hint": "Released when 2+/3 reviewers agree.",
      "trainer.wallet.this_month": "This month earnings",
    });
  });

  it("renders 3 cards with the right amounts", () => {
    render(
      <BalanceCards
        balanceInr="100.00"
        heldInr="50.00"
        thisMonthInr="300.00"
      />,
    );
    expect(screen.getByTestId("wallet-balance-available")).toHaveTextContent("100.00");
    expect(screen.getByTestId("wallet-balance-held")).toHaveTextContent("50.00");
    expect(screen.getByTestId("wallet-balance-month")).toHaveTextContent("300.00");
  });
});
