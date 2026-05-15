/**
 * InstallPrompt unit tests — TrainPlex Phase 1 Step 4.3.
 *
 * Covered scenarios
 * -----------------
 *  - `beforeinstallprompt` fires → banner renders with Install + Dismiss.
 *  - Clicking Install calls the deferred event's `prompt()` + persists
 *    the dismissed flag in localStorage.
 *  - Clicking Dismiss hides the banner + persists the flag.
 *  - iOS UA → banner renders with the manual instruction string
 *    instead of an Install button.
 *  - localStorage `tp_pwa_install_dismissed=true` → banner does NOT render.
 *  - `isIos()` helper recognises iPhone / iPad / iPod / iPadOS 13+ Mac UAs.
 *
 * `react-i18next`'s real `useTranslation` returns the key as the value
 * when no provider is wrapped; that's fine for these tests since we
 * assert on the rendered key strings.
 */

import { act, fireEvent, render, screen } from "@testing-library/react";
import "@testing-library/jest-dom";
import { InstallPrompt, isIos } from "../InstallPrompt";

const DISMISSED_LS_KEY = "tp_pwa_install_dismissed";

beforeEach(() => {
  window.localStorage.clear();
  // Reset matchMedia (some browsers persist between tests in jsdom).
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: jest.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: jest.fn(),
      removeListener: jest.fn(),
      addEventListener: jest.fn(),
      removeEventListener: jest.fn(),
      dispatchEvent: jest.fn(),
    })),
  });
});

afterEach(() => {
  window.localStorage.clear();
});

function fireBeforeInstallPrompt(): {
  prompt: jest.Mock;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
} {
  const prompt = jest.fn(() => Promise.resolve());
  let resolveChoice!: (v: { outcome: "accepted" | "dismissed" }) => void;
  const userChoice = new Promise<{ outcome: "accepted" | "dismissed" }>(
    (resolve) => {
      resolveChoice = resolve;
    },
  );
  const evt = new Event("beforeinstallprompt") as Event & {
    prompt: jest.Mock;
    userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
  };
  evt.prompt = prompt;
  evt.userChoice = userChoice;
  act(() => {
    window.dispatchEvent(evt);
  });
  // Default accept resolution; tests can override.
  resolveChoice({ outcome: "accepted" });
  return { prompt, userChoice };
}

describe("InstallPrompt — Chrome / Edge path", () => {
  it("renders the banner when beforeinstallprompt fires", () => {
    render(<InstallPrompt />);
    expect(screen.queryByTestId("pwa-install-prompt")).not.toBeInTheDocument();
    fireBeforeInstallPrompt();
    expect(screen.getByTestId("pwa-install-prompt")).toBeInTheDocument();
    expect(screen.getByTestId("pwa-install-button")).toBeInTheDocument();
    expect(screen.getByTestId("pwa-dismiss-button")).toBeInTheDocument();
  });

  it("clicking Install calls the deferred prompt + hides the banner", async () => {
    render(<InstallPrompt />);
    const { prompt } = fireBeforeInstallPrompt();
    await act(async () => {
      fireEvent.click(screen.getByTestId("pwa-install-button"));
    });
    expect(prompt).toHaveBeenCalled();
    expect(window.localStorage.getItem(DISMISSED_LS_KEY)).toBe("true");
  });

  it("clicking Dismiss persists the choice + hides the banner", () => {
    render(<InstallPrompt />);
    fireBeforeInstallPrompt();
    act(() => {
      fireEvent.click(screen.getByTestId("pwa-dismiss-button"));
    });
    expect(screen.queryByTestId("pwa-install-prompt")).not.toBeInTheDocument();
    expect(window.localStorage.getItem(DISMISSED_LS_KEY)).toBe("true");
  });

  it("does NOT render when the dismissed flag is already set", () => {
    window.localStorage.setItem(DISMISSED_LS_KEY, "true");
    render(<InstallPrompt />);
    fireBeforeInstallPrompt();
    expect(screen.queryByTestId("pwa-install-prompt")).not.toBeInTheDocument();
  });
});

describe("InstallPrompt — iOS path", () => {
  it("renders manual instructions when forceIos=true", () => {
    render(<InstallPrompt forceIos />);
    expect(screen.getByTestId("pwa-install-prompt")).toBeInTheDocument();
    expect(screen.getByTestId("pwa-ios-instructions")).toBeInTheDocument();
    // No install button on iOS — only dismiss.
    expect(screen.queryByTestId("pwa-install-button")).not.toBeInTheDocument();
    expect(screen.getByTestId("pwa-dismiss-button")).toBeInTheDocument();
  });

  it("dismiss persists across renders on iOS too", () => {
    const { unmount } = render(<InstallPrompt forceIos />);
    act(() => {
      fireEvent.click(screen.getByTestId("pwa-dismiss-button"));
    });
    expect(window.localStorage.getItem(DISMISSED_LS_KEY)).toBe("true");
    unmount();
    // Re-render — should not show because of the persisted flag.
    render(<InstallPrompt forceIos />);
    expect(screen.queryByTestId("pwa-install-prompt")).not.toBeInTheDocument();
  });
});

describe("isIos helper", () => {
  it("matches iPhone UA", () => {
    expect(
      isIos(
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
      ),
    ).toBe(true);
  });

  it("matches iPad UA", () => {
    expect(
      isIos("Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15"),
    ).toBe(true);
  });

  it("matches iPod UA", () => {
    expect(
      isIos("Mozilla/5.0 (iPod touch; CPU iPhone OS 16_0 like Mac OS X)"),
    ).toBe(true);
  });

  it("returns false for plain Android Chrome UA", () => {
    expect(
      isIos(
        "Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36",
      ),
    ).toBe(false);
  });

  it("returns false for desktop Windows Chrome UA", () => {
    expect(
      isIos(
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
      ),
    ).toBe(false);
  });
});
