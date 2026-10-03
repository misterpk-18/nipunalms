import { PageHead, Section } from "@/components/lms/ui";
import { CertificateDecisions, CertificateRegister } from "@/features/shared/certificate-register";

export function AcademicCertificates() {
  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <PageHead
        title="Certificate Eligibility"
        description="LMS Certificate Register. The fee must be cleared; the coordinator recommends, the Branch Manager approves, the number is allocated at first issue. Corrections, revocations and reinstatements are requested here and decided by someone else."
      />
      <CertificateRegister />
      <Section title="Requests and exceptions">
        <CertificateDecisions />
      </Section>
    </div>
  );
}
