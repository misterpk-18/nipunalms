import { PageHead, Section } from "@/components/lms/ui";
import { CertificateDecisions } from "@/features/shared/certificate-register";

/** Revocations, reinstatements and fee release exceptions wait for the Founder / CEO or Super Admin (Module 22 §5, §8). */
export function FounderCertificates() {
  return (
    <div className="mx-auto max-w-6xl space-y-5">
      <PageHead
        title="Certificate decisions"
        description="Requests that need the Founder / CEO or Super Admin. You never decide a request you made yourself."
      />
      <Section>
        <CertificateDecisions />
      </Section>
    </div>
  );
}
