import { PageHead, Section } from "@/components/lms/ui";
import { CertificateDecisions, CertificateRegister } from "@/features/shared/certificate-register";

export function AcademicCertificates() {
  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <PageHead
        title="Certificate Eligibility"
        description="Approve and issue certificates once the fee is cleared, and request corrections or revocations. Someone else decides those requests."
      />
      <CertificateRegister />
      <Section title="Requests and exceptions">
        <CertificateDecisions />
      </Section>
    </div>
  );
}
