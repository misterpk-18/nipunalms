/** Student accounts: find a student, see what to do next for each, and open their page. Students and their logins come from the CRM. */
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { adminApi, adminKeys, type StudentFilters } from "@/api/admin";
import { NativeSelect } from "@/components/lms/forms";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { DataTable, PageHead, QueryView, Section, StatusBadge, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import { FilterField, Pager } from "./shared";
import { NextStepButton } from "./student-actions";
import { pageOf, useUrlParams } from "./url-params";

const ACTIVATION_STATUSES = ["Account Created", "Activation Pending", "Activated", "Suspended"] as const;

export function AdminStudents() {
  const [params, setParams] = useUrlParams();
  const filters: StudentFilters = {
    ...(params["q"] ? { q: params["q"] } : {}),
    ...(params["status"] ? { activation_status: params["status"] } : {}),
    ...(params["attention"] === "true" ? { needs_attention: "true" } : {}),
    page: pageOf(params),
  };
  const query = useQuery({ queryKey: adminKeys.students(filters), queryFn: () => adminApi.students(filters), placeholderData: keepPreviousData });
  const attention = filters.needs_attention === "true";
  const filtered = !!(filters.q || filters.activation_status || attention);

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <PageHead
        title="Student accounts"
        description="Find a student and see what to do about their account. Students and their logins come from the CRM; you only help them get in."
      />
      <Section>
        <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <FilterField label="Student ID, name, mobile or email">
            <Input
              aria-label="Student ID, name, mobile, admission number or email"
              value={params["q"] ?? ""}
              onChange={(e) => setParams({ q: e.target.value, page: undefined })}
            />
          </FilterField>
          <FilterField label="Activation">
            <NativeSelect
              aria-label="Activation status"
              placeholder="Any"
              value={params["status"] ?? ""}
              options={ACTIVATION_STATUSES.map((s) => ({ value: s, label: s }))}
              onChange={(e) => setParams({ status: e.target.value, page: undefined })}
            />
          </FilterField>
          <div className="flex items-end">
            <button
              type="button"
              aria-pressed={attention}
              onClick={() => setParams({ attention: attention ? undefined : "true", page: undefined })}
              className={cn(
                "tap rounded-full border px-4 py-2 text-sm font-medium",
                attention ? "border-primary bg-primary text-primary-foreground" : "bg-card hover:bg-accent",
              )}
            >
              Needs attention
            </button>
          </div>
        </div>
        <QueryView
          query={query}
          isEmpty={(page) => page.data.length === 0}
          empty={attention ? "No student account needs attention right now." : "No students match."}
          emptyAction={
            filtered ? (
              <Button size="sm" variant="outline" onClick={() => setParams({ q: undefined, status: undefined, attention: undefined, page: undefined })}>
                Clear filters
              </Button>
            ) : undefined
          }
        >
          {(page) => (
            <>
              <DataTable
                caption="Students"
                rows={page.data}
                getKey={(s) => s.student_id}
                cols={[
                  {
                    h: "Student",
                    c: (s) => (
                      <>
                        <Link
                          to="/admin/students/$id"
                          params={{ id: String(s.student_id) }}
                          className="font-medium text-primary underline-offset-2 hover:underline"
                        >
                          {s.full_name}
                        </Link>
                        <div className="font-mono text-xs text-muted-foreground">{s.student_code}</div>
                        {s.email && <div className="text-xs text-muted-foreground">{s.email}</div>}
                      </>
                    ),
                  },
                  { h: "Branch", c: (s) => s.service_branch.branch_code },
                  { h: "Account", c: (s) => <StatusBadge domain="account" code={s.activation_status} /> },
                  {
                    h: "Suggested next step",
                    c: (s) => (
                      <div className="max-w-xs">
                        <Tag tone={s.suggested_step.attention ? "warning" : "neutral"}>{s.suggested_step.label}</Tag>
                        <p className="mt-1 text-xs text-muted-foreground">{s.suggested_step.detail}</p>
                      </div>
                    ),
                  },
                  {
                    h: "Action",
                    c: (s) => (
                      <div className="flex flex-wrap gap-1.5">
                        <NextStepButton studentId={s.student_id} step={s.suggested_step} />
                        <Button asChild variant="outline" size="sm">
                          <Link to="/admin/students/$id" params={{ id: String(s.student_id) }} aria-label={`Open ${s.full_name}`}>
                            Open
                          </Link>
                        </Button>
                      </div>
                    ),
                  },
                ]}
              />
              <Pager meta={page.meta} onPage={(p) => setParams({ page: String(p) })} />
            </>
          )}
        </QueryView>
      </Section>
      <HowThisWorks>
        <p>
          The suggested next step is worked out from the account: whether the student has a link they can use, whether sign-in is switched off, and whether any
          course is held back.
        </p>
        <p>
          Branch Managers can also send activation links for their own branch. Suspending, signing out everywhere and reactivating are Super Admin actions and
          are written to the audit log.
        </p>
      </HowThisWorks>
    </div>
  );
}
