import { Link, createFileRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { BadgeCheck, CircleAlert, CircleX, SearchX } from "lucide-react";
import { certificatesApi, type Verification } from "@/api/certificates";
import { ApiError } from "@/api/client";
import { AuthPage } from "@/components/lms/auth-page";
import { KeyValue, LoadingSkeleton, Section } from "@/components/lms/ui";
import { fmtDate } from "@/features/shared/format";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/verify/$number")({
  validateSearch: (search: Record<string, unknown>): { version?: number } => (Number(search["version"]) > 0 ? { version: Number(search["version"]) } : {}),
  component: VerifyCertificate,
});

const RESULT = {
  "Valid — Current Version": {
    icon: BadgeCheck,
    title: "Valid certificate",
    line: "This certificate was issued by Nipuna Technologies and is current.",
    tone: "border-success/40 bg-success-soft text-success",
  },
  Revoked: {
    icon: CircleX,
    title: "Revoked certificate",
    line: "Nipuna Technologies has withdrawn this certificate. Do not accept it.",
    tone: "border-danger/40 bg-danger-soft text-danger",
  },
  Superseded: {
    icon: CircleAlert,
    title: "Replaced by a newer copy",
    line: "This copy was corrected and replaced. Ask the holder for the newest copy.",
    tone: "border-warning/40 bg-warning-soft text-warning",
  },
} as const;

/** Public certificate check: one large answer (valid, revoked or replaced), then only the public facts about the holder. */
function VerifyCertificate() {
  const { number } = Route.useParams();
  const { version } = Route.useSearch();
  const query = useQuery({ queryKey: ["verify", number, version], queryFn: () => certificatesApi.verify(number, version), retry: false });
  const notFound = query.error instanceof ApiError && query.error.status === 404;

  return (
    <AuthPage>
      <Section title="Check a certificate">
        {query.isPending ? (
          <LoadingSkeleton />
        ) : notFound ? (
          <NotFound number={number} />
        ) : query.isError ? (
          <p role="alert" className="text-sm text-danger">
            We could not check this certificate right now. Please try again in a moment.
          </p>
        ) : (
          <Found c={query.data} />
        )}
      </Section>
    </AuthPage>
  );
}

function Found({ c }: { c: Verification }) {
  const result = RESULT[c.state];
  const Icon = result.icon;
  return (
    <div className="space-y-4">
      <div className={cn("rounded-xl border p-5 text-center", result.tone)} role="status">
        <Icon className="mx-auto size-12" aria-hidden />
        <p className="mt-2 text-2xl font-bold">{result.title}</p>
        <p className="mt-1 text-sm">{result.line}</p>
        {c.current_version && c.state !== "Valid — Current Version" && <p className="mt-1 text-sm">The newest copy is version {c.current_version.version}.</p>}
      </div>
      <KeyValue
        items={[
          ["Certificate number", `${c.certificate_number} · version ${c.version}`],
          ["Holder", c.holder_name],
          ["Certificate", `${c.certificate_type}: ${c.course.title}`],
          ["Branch", c.branch.branch_name],
          ["Issued", c.issue_date ? fmtDate(c.issue_date) : "—"],
          ...(c.original_issue_date && c.version > 1 ? ([["First issued", fmtDate(c.original_issue_date)]] as [string, string][]) : []),
        ]}
      />
    </div>
  );
}

function NotFound({ number }: { number: string }) {
  return (
    <div className="space-y-4 rounded-xl border p-5 text-center">
      <SearchX className="mx-auto size-12 text-muted-foreground" aria-hidden />
      <p className="text-2xl font-bold">Certificate not found</p>
      <p className="text-sm text-muted-foreground">
        We have no certificate numbered <span className="font-mono">{number}</span>. Check the number on the certificate and try again. If it still isn't found,
        the certificate may not be genuine: contact the branch that says it issued it.
      </p>
      <Link to="/login" className="text-sm text-primary underline-offset-4 hover:underline">
        Go to Nipuna LMS
      </Link>
    </div>
  );
}
