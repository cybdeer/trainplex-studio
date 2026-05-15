import i18n, { SUPPORTED_LANGUAGES } from "../config";

describe("i18n config", () => {
  beforeAll(async () => {
    // Ensure init has resolved before assertions run.
    if (!i18n.isInitialized) {
      await new Promise<void>((resolve) => i18n.on("initialized", () => resolve()));
    }
  });

  it("declares en + hi as the supported languages", () => {
    expect(SUPPORTED_LANGUAGES).toEqual(["en", "hi"]);
  });

  it("registers en and hi resources under the common namespace", () => {
    const enBundle = i18n.getResourceBundle("en", "common");
    const hiBundle = i18n.getResourceBundle("hi", "common");
    expect(enBundle).toBeDefined();
    expect(hiBundle).toBeDefined();
    expect(enBundle.app.name).toBe("TrainPlex Studio");
    expect(hiBundle.app.name).toBe("TrainPlex Studio");
  });

  it("resolves t('app.name') to the English brand string by default", async () => {
    await i18n.changeLanguage("en");
    expect(i18n.t("app.name")).toBe("TrainPlex Studio");
  });

  it("switches to Hindi and resolves trainer.dashboard_title in Devanagari", async () => {
    await i18n.changeLanguage("hi");
    expect(i18n.t("trainer.dashboard_title")).toBe("आज के कार्य");
  });

  it("interpolates the tier variable into the Hindi locked-task string", async () => {
    await i18n.changeLanguage("hi");
    expect(i18n.t("trainer.task_locked_tier", { tier: "silver" })).toBe(
      "बंद — silver में जाने पर खुलेगा",
    );
  });

  afterAll(async () => {
    // Reset to English so unrelated tests aren't affected by the Hindi switch above.
    await i18n.changeLanguage("en");
  });
});
