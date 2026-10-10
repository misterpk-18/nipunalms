import { PageHead, Section } from "@/components/lms/ui";
import { CertificateDecisions, CertificateRegister } from "@/features/shared/certificate-register";

export function AcademicCertificates() {
  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <PageHead
        title="Certificate Eligibility"
        description="LMS Certificate Register. The fee must be cleared; the Branch Manager approves (recommending in the same step) and issues; the number is allocated at first issue. Corrections, revocations and reinstatements are requested here and decided by someone else (a Super Admin when a Branch Manager asks)."
      />
      <CertificateRegister />
      <Section title="Requests and exceptions">
        <CertificateDecisions />
      </Section>
    </div>
  );
}
