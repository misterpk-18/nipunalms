import { PageHead } from "@/components/lms/ui";
import { CertificateRegister } from "@/features/shared/certificate-register";

export function AcademicCertificates() {
  return (
    <div className="mx-auto max-w-7xl space-y-4">
      <PageHead
        title="Certificate Eligibility"
        description="LMS Certificate Register. The coordinator recommends, the Branch Manager approves, the number is allocated at first issue."
      />
      <CertificateRegister />
    </div>
  );
}
