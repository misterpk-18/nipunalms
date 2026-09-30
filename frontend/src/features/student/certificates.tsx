import { useMyCertificates } from "@/api/certificates";
import { Note, PageHead, QueryView, StatusNote } from "@/components/lms/ui";
import { CertificateTable } from "@/features/shared/certificate-register";
import { useT } from "@/lib/i18n";

export function Certificates() {
  const t = useT();
  const query = useMyCertificates();
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <PageHead title={t("certificates")} description="LMS Certificate Register · Course Completion and Internship certificates" />
      <Note>
        Certificates come from a completion review, not from a percentage. The number is allocated when a certificate is issued and stays the same if it is
        reissued.
      </Note>
      <QueryView query={query}>
        {(data) => (
          <>
            <h2 className="text-lg font-semibold">My certificates</h2>
            <CertificateTable rows={data.certificates} withActions={false} />
            {data.configuration_pending.map((p) => (
              <StatusNote key={p.enrolment.enrolment_id} state="Pending Verification">
                {p.enrolment.course.course_code} (complimentary): Configuration Pending — {p.message.toLowerCase()}.
              </StatusNote>
            ))}
          </>
        )}
      </QueryView>
    </div>
  );
}
