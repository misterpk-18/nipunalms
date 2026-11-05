import { createFileRoute } from "@tanstack/react-router";
import { AuthPage } from "@/components/lms/auth-page";
import { Section } from "@/components/lms/ui";
import { VerifyForm } from "@/features/shared/verify-form";

export const Route = createFileRoute("/verify/")({
  component: VerifyStart,
});

/** Public: anyone can type the number printed on a Nipuna certificate and see whether it is genuine and current. */
function VerifyStart() {
  return (
    <AuthPage>
      <Section title="Check a certificate">
        <p className="mb-3 text-sm text-muted-foreground">
          Type the certificate number to see whether Nipuna Technologies issued it and whether it is still valid. The QR code on the certificate opens the same
          check.
        </p>
        <VerifyForm />
      </Section>
    </AuthPage>
  );
}
