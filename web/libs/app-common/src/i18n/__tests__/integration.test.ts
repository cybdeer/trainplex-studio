import i18n from "../config";

/**
 * Step 1.4-C — integration coverage for the wider i18n surface.
 *
 * `config.test.ts` already exercises the core "init + Hindi switch" path. This
 * file adds the assertions called out in the Week 3 task spec that weren't
 * already covered:
 *   - en-after-hi round trip (switching back to English actually restores EN strings,
 *     i.e. the resource bundle isn't lost or shadowed by the language change)
 *   - interpolation works on the English side too (the existing test only checked Hindi)
 *   - the newly-added admin / home keys (admin.add_members, home.welcome) resolve
 *     correctly in both locales, so we don't ship parity-broken bundles
 */
describe("i18n integration (Step 1.4-C surface)", () => {
  beforeAll(async () => {
    if (!i18n.isInitialized) {
      await new Promise<void>((resolve) => i18n.on("initialized", () => resolve()));
    }
  });

  afterAll(async () => {
    // Reset to English so unrelated test files aren't affected by language drift.
    await i18n.changeLanguage("en");
  });

  it("resolves app.name to the brand string in English by default", async () => {
    await i18n.changeLanguage("en");
    expect(i18n.t("app.name")).toBe("TrainPlex Studio");
  });

  it("round-trips hi -> en cleanly (English bundle is not lost after Hindi switch)", async () => {
    await i18n.changeLanguage("hi");
    expect(i18n.t("trainer.dashboard_title")).toBe("आज के कार्य");

    await i18n.changeLanguage("en");
    expect(i18n.t("trainer.dashboard_title")).toBe("Today's tasks");
    // Sanity: switching back to English should also restore admin.create_project.
    expect(i18n.t("admin.create_project")).toBe("Create Project");
  });

  it("interpolates the tier variable into the English locked-task string", async () => {
    await i18n.changeLanguage("en");
    expect(i18n.t("trainer.task_locked_tier", { tier: "silver" })).toBe(
      "Locked — promote to silver to unlock",
    );
  });

  it("resolves the newly-added admin.add_members key in both locales", async () => {
    await i18n.changeLanguage("en");
    expect(i18n.t("admin.add_members")).toBe("Add Members");
    await i18n.changeLanguage("hi");
    expect(i18n.t("admin.add_members")).toBe("सदस्य जोड़ें");
  });

  it("resolves the newly-added home.welcome key in both locales", async () => {
    await i18n.changeLanguage("en");
    expect(i18n.t("home.welcome")).toBe("Welcome");
    await i18n.changeLanguage("hi");
    expect(i18n.t("home.welcome")).toBe("स्वागत है");
  });

  // Phase 1 Step 1.4-E + Step 13 — trainer Batch + Settings keys must
  // land in both locales. Single-key spot-check is enough; the parity-
  // lock test below already enforces structural equality.
  it("resolves trainer.batch.title in both locales", async () => {
    await i18n.changeLanguage("en");
    expect(i18n.t("trainer.batch.title")).toBe("Today's Batch");
    await i18n.changeLanguage("hi");
    expect(i18n.t("trainer.batch.title")).toBe("आज का बैच");
  });

  it("resolves trainer.settings.* labels in both locales", async () => {
    await i18n.changeLanguage("en");
    expect(i18n.t("trainer.settings.profile")).toBe("Profile");
    expect(i18n.t("trainer.settings.security")).toBe("Security");
    expect(i18n.t("trainer.settings.notifications")).toBe("Notifications");
    expect(i18n.t("trainer.settings.payout")).toBe("Payout");
    expect(i18n.t("trainer.settings.preferences")).toBe("Preferences");

    await i18n.changeLanguage("hi");
    expect(i18n.t("trainer.settings.profile")).toBe("प्रोफ़ाइल");
    expect(i18n.t("trainer.settings.security")).toBe("सुरक्षा");
    expect(i18n.t("trainer.settings.notifications")).toBe("अधिसूचनाएँ");
    expect(i18n.t("trainer.settings.payout")).toBe("भुगतान");
    expect(i18n.t("trainer.settings.preferences")).toBe("प्राथमिकताएँ");
  });

  it("interpolates the trainer.batch.progress vars in both locales", async () => {
    await i18n.changeLanguage("en");
    expect(i18n.t("trainer.batch.progress", { done: 3, total: 10 })).toBe(
      "3/10 done",
    );
    await i18n.changeLanguage("hi");
    expect(i18n.t("trainer.batch.progress", { done: 3, total: 10 })).toBe(
      "3/10 पूरे",
    );
  });

  it("keeps en + hi resource bundles structurally parity-locked", () => {
    const enBundle = i18n.getResourceBundle("en", "common");
    const hiBundle = i18n.getResourceBundle("hi", "common");

    // Recursively flatten "a.b.c" key paths so we can diff parity cheaply.
    const flatten = (obj: Record<string, unknown>, prefix = ""): string[] => {
      const acc: string[] = [];
      for (const [key, value] of Object.entries(obj)) {
        const path = prefix ? `${prefix}.${key}` : key;
        if (value && typeof value === "object" && !Array.isArray(value)) {
          acc.push(...flatten(value as Record<string, unknown>, path));
        } else {
          acc.push(path);
        }
      }
      return acc;
    };

    const enKeys = flatten(enBundle).sort();
    const hiKeys = flatten(hiBundle).sort();
    expect(enKeys).toEqual(hiKeys);
  });
});
