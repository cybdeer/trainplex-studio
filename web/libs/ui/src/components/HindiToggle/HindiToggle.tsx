import { useTranslation } from "react-i18next";

export function HindiToggle() {
  const { i18n } = useTranslation();
  const current = i18n.language?.startsWith("hi") ? "hi" : "en";
  const toggle = () => i18n.changeLanguage(current === "hi" ? "en" : "hi");
  return (
    <button
      type="button"
      onClick={toggle}
      className="tp-hindi-toggle"
      aria-label={`Switch language to ${current === "hi" ? "English" : "Hindi"}`}
    >
      {current === "hi" ? "EN" : "हि"}
    </button>
  );
}

export default HindiToggle;
