import { createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { certificatesApi } from "@/api/certificates";
import { AuthPage } from "@/components/lms/auth-page";
import { KeyValue, QueryView, Section, StatusNote } from "@/components/lms/ui";
import { fmtDate } from "@/features/shared/format";

export const Route = createFileRoute("/verify/$number")({
  validateSearch: (search: Record<string, unknown>): { version?: number } =>
    Number(search["version"]) > 0 ? { version: Number(search["version"]) } : {},
  component: VerifyCertificate,
});

/** Public certificate verification (Module 22 §9): the presented version's state, never more than the public facts. */
function VerifyCertificate() {
  const { number } = Route.useParams();
  const { version } = Route.useSearch();
  const query = useQuery({ queryKey: ["verify", number, version], queryFn: () => certificatesApi.verify(number, version), retry: false });
  return (
    <AuthPage>
      <Section title="Certificate verification">
        <QueryView query={query}>
          {(c) => (
            <div className="space-y-3">
              <StatusNote state={c.state === "Valid — Current Version" ? "Saved" : c.state === "Revoked" ? "Error" : "Stale"}>
                {c.state}
                {c.current_version && ` — the current copy is version ${c.current_version.version} (${c.current_version.state})`}
              </StatusNote>
              <KeyValue
                items={[
                  ["Certificate number", `${c.certificate_number} · version ${c.version}`],
                  ["Holder", c.holder_name],
                  ["Certificate", `${c.certificate_type} — ${c.course.title} (${c.course.course_code})`],
                  ["Branch", c.branch.branch_name],
                  ["Issued", c.issue_date ? fmtDate(c.issue_date) : "—"],
                  ["Originally issued", c.original_issue_date ? fmtDate(c.original_issue_date) : "—"],
                ]}
              />
            </div>
          )}
        </QueryView>
      </Section>
    </AuthPage>
  );
}
