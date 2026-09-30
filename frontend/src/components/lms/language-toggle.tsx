import { useLanguage } from "@/lib/i18n";
import { cn } from "@/lib/utils";

/** EN / తెలుగు switch; the choice is remembered per user. */
export function LanguageToggle() {
  const { lang, setLang } = useLanguage();
  const option = (value: "en" | "te", label: string) => (
    <button
      lang={value}
      onClick={() => setLang(value)}
      aria-pressed={lang === value}
      className={cn("tap px-2 text-xs font-medium", lang === value ? "bg-primary text-primary-foreground" : "bg-card text-foreground")}
    >
      {label}
    </button>
  );
  return (
    <div role="group" aria-label="Language / భాష" className="flex overflow-hidden rounded-lg border border-navy-muted">
      {option("en", "EN")}
      {option("te", "తెలుగు")}
    </div>
  );
}
