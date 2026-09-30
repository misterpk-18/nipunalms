import type { ReactNode } from "react";
import { ShieldCheck } from "lucide-react";
import { LanguageToggle } from "@/components/lms/language-toggle";
import { useDocumentLanguage } from "@/lib/i18n";

/** Frame for the public screens (sign in, activation, forced password change): navy bar, language toggle, centred content. */
export function AuthPage({ children, wide }: { children: ReactNode; wide?: boolean }) {
  useDocumentLanguage(true);
  return (
    <div className="min-h-screen">
      <header className="border-b bg-navy text-navy-foreground">
        <div className="flex h-14 items-center gap-2 px-3 sm:px-5">
          <span className="grid size-8 place-items-center rounded-lg bg-primary text-primary-foreground">
            <ShieldCheck className="size-5" aria-hidden />
          </span>
          <span className="font-semibold">Nipuna LMS</span>
          <div className="ml-auto">
            <LanguageToggle />
          </div>
        </div>
      </header>
      <main className={wide ? "mx-auto grid max-w-5xl gap-6 px-4 py-6 lg:grid-cols-2" : "mx-auto max-w-md px-4 py-6"}>{children}</main>
    </div>
  );
}
