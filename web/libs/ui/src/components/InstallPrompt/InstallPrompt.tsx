/**
 * InstallPrompt — TrainPlex PWA "Add to home screen" banner.
 *
 * Phase 1 Step 4.3. Goal: every trainer who opens TrainPlex on a phone
 * gets a clear nudge to install the PWA so their next visit takes <2s
 * (cached shell) rather than the cold-fetch network roundtrip.
 *
 * Behaviour
 * ---------
 *  1. **Standard PWA path** — Chrome / Edge / Samsung Internet fire a
 *     `beforeinstallprompt` event when the install criteria are met.
 *     We capture the event, suppress the browser's default mini-infobar,
 *     and render our own banner with an "Install" CTA. Clicking the CTA
 *     calls `event.prompt()` which then runs the native install dialog.
 *  2. **iOS Safari path** — Safari has no programmatic install. We detect
 *     the iOS user agent and render an instructional banner instead:
 *     "Tap the Share button below, then tap Add to Home Screen". No CTA
 *     — only a dismiss button.
 *  3. **Already installed** — `display-mode: standalone` media query
 *     short-circuits rendering (the user is already in PWA mode).
 *  4. **Dismissal** — once dismissed, the choice persists in localStorage
 *     under `tp_pwa_install_dismissed` so the trainer isn't nagged on
 *     every page load.
 *
 * Accessibility
 * -------------
 *  - The banner is `role="region"` with an `aria-label` that announces
 *    "TrainPlex install prompt" to screen readers.
 *  - The Install button is the only positive action; dismiss is secondary
 *    so screen-reader users hit Install first when tabbing.
 *  - Touch targets ≥ 44×44px (per Apple HIG + WCAG 2.1 AA).
 */

import { useTranslation } from "react-i18next";
import { useEffect, useState } from "react";
import styles from "./InstallPrompt.module.css";

/**
 * The `BeforeInstallPromptEvent` is not in lib.dom.d.ts because it's a
 * Chrome-ism. We declare just the shape we touch.
 */
interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

const DISMISSED_LS_KEY = "tp_pwa_install_dismissed";

/** UA-based iOS detection. Touch-friendly — covers iPhone + iPad. */
export function isIos(ua: string = typeof navigator !== "undefined" ? navigator.userAgent : ""): boolean {
  if (!ua) return false;
  // iPadOS 13+ reports as Mac — augment with `ontouchend` heuristic.
  const isIPadOs13Plus =
    ua.includes("Mac") &&
    typeof navigator !== "undefined" &&
    (navigator.maxTouchPoints ?? 0) > 1;
  return /iPad|iPhone|iPod/.test(ua) || isIPadOs13Plus;
}

/** Check if the app is already running in standalone (installed) mode. */
function isStandalone(): boolean {
  if (typeof window === "undefined") return false;
  if (window.matchMedia?.("(display-mode: standalone)").matches) return true;
  // iOS pre-PWA media-query support uses a non-standard `navigator.standalone`.
  const navWithIos = navigator as unknown as { standalone?: boolean };
  return navWithIos.standalone === true;
}

function isDismissed(): boolean {
  try {
    return localStorage.getItem(DISMISSED_LS_KEY) === "true";
  } catch {
    return false;
  }
}

function markDismissed() {
  try {
    localStorage.setItem(DISMISSED_LS_KEY, "true");
  } catch {
    // Private browsing / Safari quirks — silently ignore. Next reload
    // re-shows the banner; not the end of the world.
  }
}

export interface InstallPromptProps {
  /** Override the auto-detected iOS check (useful in tests / Storybook). */
  forceIos?: boolean;
  /** Skip the standalone short-circuit (testing only). */
  ignoreStandalone?: boolean;
  /** Callback fired when the user installs or dismisses. */
  onChoice?: (choice: "installed" | "dismissed") => void;
}

export function InstallPrompt({
  forceIos,
  ignoreStandalone = false,
  onChoice,
}: InstallPromptProps) {
  const { t } = useTranslation();
  const [deferredPrompt, setDeferredPrompt] = useState<BeforeInstallPromptEvent | null>(null);
  const [visible, setVisible] = useState(false);

  // iOS handling — set once on mount.
  const iosDetected = forceIos ?? isIos();

  useEffect(() => {
    if (!ignoreStandalone && isStandalone()) return; // already installed
    if (isDismissed()) return;

    if (iosDetected) {
      // No event needed; show banner immediately so user can follow
      // the Share → Add to Home Screen instructions.
      setVisible(true);
      return;
    }

    // Standard Chrome / Edge path.
    const handler = (event: Event) => {
      // Prevent the browser's default mini-infobar so we control the UX.
      event.preventDefault();
      setDeferredPrompt(event as BeforeInstallPromptEvent);
      setVisible(true);
    };
    window.addEventListener("beforeinstallprompt", handler);
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, [iosDetected, ignoreStandalone]);

  if (!visible) return null;

  const handleInstall = async () => {
    if (!deferredPrompt) return;
    await deferredPrompt.prompt();
    const result = await deferredPrompt.userChoice;
    setDeferredPrompt(null);
    setVisible(false);
    markDismissed();
    onChoice?.(result.outcome === "accepted" ? "installed" : "dismissed");
  };

  const handleDismiss = () => {
    markDismissed();
    setVisible(false);
    onChoice?.("dismissed");
  };

  return (
    <div
      className={styles.banner}
      role="region"
      aria-label={t("pwa.install_title")}
      data-testid="pwa-install-prompt"
    >
      <div className={styles.icon} aria-hidden="true">
        TP
      </div>
      {iosDetected ? (
        <div className={styles.iosCopy}>
          <div className={styles.title}>{t("pwa.install_title")}</div>
          <div className={styles.iosInstructions} data-testid="pwa-ios-instructions">
            {t("pwa.ios_instructions")}
          </div>
        </div>
      ) : (
        <div className={styles.copy}>
          <div className={styles.title}>{t("pwa.install_title")}</div>
          <div className={styles.body}>{t("pwa.install_body")}</div>
        </div>
      )}
      <div className={styles.actions}>
        {!iosDetected && (
          <button
            type="button"
            className={styles.installBtn}
            onClick={handleInstall}
            data-testid="pwa-install-button"
          >
            {t("pwa.install_button")}
          </button>
        )}
        <button
          type="button"
          className={styles.dismissBtn}
          onClick={handleDismiss}
          data-testid="pwa-dismiss-button"
        >
          {t("pwa.install_dismiss")}
        </button>
      </div>
    </div>
  );
}

export default InstallPrompt;
