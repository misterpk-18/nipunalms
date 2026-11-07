import type { ReactNode } from "react";
import { LanguageToggle } from "@/components/lms/language-toggle";
import { useDocumentLanguage } from "@/lib/i18n";

/** Frame for the public screens (sign in, activation, forced password change): navy bar, language toggle, centred content. */
export function AuthPage({ children, wide }: { children: ReactNode; wide?: boolean }) {
  useDocumentLanguage(true);
  return (
    <div className="min-h-screen">
      <header className="border-b bg-navy text-navy-foreground">
        <div className="flex h-14 items-center gap-2 px-3 sm:px-5">
          <img src="/nipuna-logo.png" alt="Nipuna Technologies" className="h-8 w-auto rounded-md" />
          <span className="font-semibold">LMS</span>
          <div className="ml-auto">
            <LanguageToggle />
          </div>
        </div>
      </header>
      <main className={wide ? "mx-auto grid max-w-5xl gap-6 px-4 py-6 lg:grid-cols-2" : "mx-auto max-w-md px-4 py-6"}>{children}</main>
    </div>
  );
}
