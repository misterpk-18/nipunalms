import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { useQuery } from "@tanstack/react-query";
import { KeyRound, LockOpen, Plus, Send, UserCheck, UserMinus, X } from "lucide-react";
import { adminApi, adminKeys, type SplitHandout, type StaffScope, type StaffUser, type StaffUserWithPassword, type UserFilters } from "@/api/admin";
import type { RoleCode } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field, NativeSelect, applyServerErrors } from "@/components/lms/forms";
import { ConfirmDialog } from "@/components/lms/confirm-dialog";
import { DataTable, Note, PageHead, QueryView, Section, StatusBadge } from "@/components/lms/ui";
import { useApiMutation } from "@/lib/mutation";
import { FilterField, FormDialog, Pager, SecretDialog, type Secret } from "@/features/shared/form-parts";
import { istDateTime, whatsappLine } from "./format";
import { useUrlParams } from "@/features/shared/url-params";

/** What each role can do, in one line: shown beside the role in the picker so nobody has to remember. */
const STAFF_ROLES: { value: RoleCode; label: string; companyWide: boolean; description: string }[] = [
  { value: "TRAINER", label: "Trainer", companyWide: false, description: "Runs classes, marks attendance and grades work for their batches." },
  {
    value: "BRANCH_MANAGER",
    label: "Branch Manager",
    companyWide: false,
    description: "Runs one branch: batches, schedule, results, certificates and student support.",
  },
  {
    value: "SUPER_ADMIN",
    label: "Super Admin",
    companyWide: true,
    description: "Looks after people and access, the CRM link, setup and health, in every branch.",
  },
  {
    value: "FOUNDER_CEO",
    label: "Founder / CEO",
    companyWide: true,
    description: "Everything the Super Admin can do, plus approvals, across all branches.",
  },
];

const roleOptions = STAFF_ROLES.map((r) => ({ value: r.value, label: `${r.label} — ${r.description}` }));
const roleHint = (role: RoleCode | "") => STAFF_ROLES.find((r) => r.value === role)?.description;

type Action =
  { kind: "create" } | { kind: "revoke"; user: StaffUser; scope: StaffScope } | { kind: "deactivate"; user: StaffUser } | { kind: "unlock"; user: StaffUser };

/** What to show once after a create, invite or reset: the invite link, the temporary password, or both. */
function secretsOf(user: StaffUserWithPassword): Secret[] {
  return [
    ...(user.invite_path ? [{ label: "Invite link", value: `${window.location.origin}${user.invite_path}` }] : []),
    ...(user.temporary_password ? [{ label: "Temporary password", value: user.temporary_password }] : []),
  ];
}

function secretNote(user: StaffUserWithPassword): string {
  if (user.invite_path) {
    return `${whatsappLine(user.whatsapp ?? { state: "Skipped", note: null }, user.full_name)} The link works once. ${
      user.temporary_password ? "Or give the temporary password. " : ""
    }Either way ${user.full_name} chooses their own password. Shown only now.`;
  }
  return `Give ${user.email} this temporary password now. It is shown once and cannot be retrieved; they must change it at first sign-in.`;
}

const IDS = adminKeys.usersAll;

/** Users & Access: staff accounts and their role scopes. Students are created by the CRM, never here. */
/** `canEdit` comes from the route; Super Admin and Founder both manage accounts and hand out links. */
export function AdminUsers({ canEdit }: { canEdit: boolean }) {
  const [urlParams, setUrlParams] = useUrlParams();
  const [filters, setFilters] = useState<UserFilters>({
    is_active: "true",
    ...(urlParams["q"] ? { q: urlParams["q"] } : {}),
    ...(urlParams["locked"] === "true" ? { locked: "true" } : {}),
  });
  const [action, setAction] = useState<Action | null>(urlParams["add"] === "1" && canEdit ? { kind: "create" } : null);
  useEffect(() => {
    // Links from Home and the Audit log arrive with ?add=1, ?locked=true or ?q=: they have been applied, so the address goes back to plain
    if (urlParams["add"] || urlParams["locked"] || urlParams["q"]) setUrlParams({ add: undefined, locked: undefined, q: undefined });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const [secret, setSecret] = useState<{ title: string; user: StaffUserWithPassword } | null>(null);
  const query = useQuery({ queryKey: adminKeys.users(filters), queryFn: () => adminApi.users(filters) });

  const reactivate = useApiMutation((user: StaffUser) => adminApi.reactivateUser(user.user_id), {
    success: (u) => `${u.full_name} reactivated`,
    invalidate: [[...IDS]],
  });
  const invite = useApiMutation((user: StaffUser) => adminApi.sendInvite(user.user_id), {
    invalidate: [[...IDS]],
    onSuccess: (user) => setSecret({ title: `New invite for ${user.full_name}`, user }),
  });
  const reset = useApiMutation((user: StaffUser) => adminApi.resetPassword(user.user_id), {
    invalidate: [[...IDS]],
    onSuccess: (user) => setSecret({ title: `Password reset for ${user.full_name}`, user }),
  });

  return (
    <>
      <PageHead
        title="Staff accounts"
        description="Staff logins: add staff (one account per role), take away access, unlock accounts and send invites. Students are created by the CRM and looked after under Student accounts."
        actions={
          canEdit && (
            <Button onClick={() => setAction({ kind: "create" })}>
              <Plus className="size-4" /> Add staff user
            </Button>
          )
        }
      />
      <div className="space-y-4">
        <Section>
          <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <FilterField label="Search name or email">
              <Input aria-label="Search name or email" value={filters.q ?? ""} onChange={(e) => setFilters({ ...filters, q: e.target.value, page: 1 })} />
            </FilterField>
            <FilterField label="Role">
              <NativeSelect
                aria-label="Role"
                placeholder="All roles"
                value={filters.role_code ?? ""}
                options={STAFF_ROLES.map((r) => ({ value: r.value, label: r.label }))}
                onChange={(e) => setFilters({ ...filters, role_code: e.target.value, page: 1 })}
              />
            </FilterField>
            <FilterField label="Status">
              <NativeSelect
                aria-label="Status"
                placeholder="All"
                value={filters.locked === "true" ? "locked" : (filters.is_active ?? "")}
                options={[
                  { value: "true", label: "Active" },
                  { value: "locked", label: "Locked (too many wrong passwords)" },
                  { value: "false", label: "Deactivated" },
                ]}
                onChange={(e) => {
                  const v = e.target.value;
                  const { locked: _locked, is_active: _active, ...rest } = filters;
                  setFilters({ ...rest, ...(v === "locked" ? { locked: "true" } : v ? { is_active: v } : {}), page: 1 });
                }}
              />
            </FilterField>
          </div>
          <QueryView query={query} isEmpty={(page) => page.data.length === 0} empty="No staff users match.">
            {(page) => (
              <>
                <DataTable
                  caption="Staff users"
                  rows={page.data}
                  getKey={(u) => u.user_id}
                  cols={[
                    {
                      h: "User",
                      c: (u) => (
                        <>
                          <div className="font-medium">{u.full_name}</div>
                          <div className="text-xs text-muted-foreground">{u.email}</div>
                        </>
                      ),
                    },
                    {
                      h: "Roles",
                      c: (u) => (
                        <ul className="flex flex-wrap gap-1.5">
                          {u.scopes.map((s) => (
                            <li key={s.scope_id} className="inline-flex items-center gap-1 rounded-full border bg-muted px-2 py-0.5 text-xs">
                              {s.role_name}
                              {s.branch_code ? ` · ${s.branch_code}` : " · all branches"}
                              {s.expires_at && ` · until ${istDateTime(s.expires_at)}`}
                              {canEdit && (
                                <button
                                  type="button"
                                  aria-label={`Revoke ${s.role_name} ${s.branch_code ?? ""} from ${u.full_name}`}
                                  className="rounded-full p-0.5 hover:bg-accent"
                                  onClick={() => setAction({ kind: "revoke", user: u, scope: s })}
                                >
                                  <X className="size-3" />
                                </button>
                              )}
                            </li>
                          ))}
                          {u.scopes.length === 0 && <span className="text-xs text-muted-foreground">No active role</span>}
                        </ul>
                      ),
                    },
                    {
                      h: "Status",
                      c: (u) => (
                        <div className="flex flex-wrap gap-1">
                          <StatusBadge domain="account" code={u.is_active ? "Active" : "Deactivated"} />
                          {u.must_change_password && <StatusBadge domain="account" code="Must change password" />}
                          {u.is_locked && <StatusBadge domain="account" code="Locked" />}
                          {u.is_locked && u.locked_until && <span className="text-xs text-muted-foreground">until {istDateTime(u.locked_until)}</span>}
                        </div>
                      ),
                    },
                    { h: "Last sign-in", c: (u) => istDateTime(u.last_login_at) },
                    ...(canEdit
                      ? [
                          {
                            h: "Actions",
                            c: (u: StaffUser) => (
                              <div className="flex flex-wrap gap-1.5">
                                {u.is_locked && (
                                  <Button size="sm" onClick={() => setAction({ kind: "unlock", user: u })} aria-label={`Unlock ${u.full_name}`}>
                                    <LockOpen className="size-3.5" /> Unlock
                                  </Button>
                                )}
                                {u.must_change_password && u.is_active && (
                                  <ConfirmDialog
                                    title={`${u.last_login_at ? "Send" : "Resend"} ${u.full_name} an invite?`}
                                    consequence="A new one-time link goes to their WhatsApp number so they can choose a password. Any earlier link stops working."
                                    confirmLabel={u.last_login_at ? "Send invite" : "Resend invite"}
                                    onConfirm={() => invite.mutateAsync(u).then(() => undefined)}
                                  >
                                    <Button variant="outline" size="sm" aria-label={`${u.last_login_at ? "Send" : "Resend"} invite to ${u.full_name}`}>
                                      <Send className="size-3.5" /> {u.last_login_at ? "Send invite" : "Resend invite"}
                                    </Button>
                                  </ConfirmDialog>
                                )}
                                <ConfirmDialog
                                  title={`Reset password for ${u.full_name}?`}
                                  consequence="A new temporary password is shown once and every session of this person ends. They must change the password at their next sign-in. (People can also reset their own password from the sign-in page.)"
                                  confirmLabel="Reset password"
                                  onConfirm={() => reset.mutateAsync(u).then(() => undefined)}
                                >
                                  <Button variant="outline" size="sm" aria-label={`Reset password for ${u.full_name}`}>
                                    <KeyRound className="size-3.5" /> Reset
                                  </Button>
                                </ConfirmDialog>
                                {u.is_active ? (
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => setAction({ kind: "deactivate", user: u })}
                                    aria-label={`Deactivate ${u.full_name}`}
                                  >
                                    <UserMinus className="size-3.5" /> Deactivate
                                  </Button>
                                ) : (
                                  <Button variant="outline" size="sm" onClick={() => reactivate.mutate(u)} aria-label={`Reactivate ${u.full_name}`}>
                                    <UserCheck className="size-3.5" /> Reactivate
                                  </Button>
                                )}
                              </div>
                            ),
                          },
                        ]
                      : []),
                  ]}
                />
                <Pager meta={page.meta} onPage={(p) => setFilters({ ...filters, page: p })} />
              </>
            )}
          </QueryView>
        </Section>
        <Note>
          Each account holds one role. Someone who works in two roles has two accounts, each with its own email and sign-in. Role changes, password resets,
          unlocking and deactivation ask for your password again and are written to the audit log.
        </Note>
        <HandoutSection />
      </div>

      {action?.kind === "create" && (
        <CreateUserDialog
          onClose={() => setAction(null)}
          onCreated={(user) => {
            setAction(null);
            setSecret({ title: `${user.full_name} created`, user });
          }}
        />
      )}
      {action?.kind === "revoke" && (
        <ReasonDialog title={`Revoke ${action.scope.role_name}`} user={action.user} scope={action.scope} onClose={() => setAction(null)} />
      )}
      {action?.kind === "deactivate" && <ReasonDialog title="Deactivate account" user={action.user} onClose={() => setAction(null)} />}
      {action?.kind === "unlock" && <ReasonDialog title="Unlock account" user={action.user} unlock onClose={() => setAction(null)} />}
      {secret && <SecretDialog title={secret.title} description={secretNote(secret.user)} secrets={secretsOf(secret.user)} onClose={() => setSecret(null)} />}
    </>
  );
}

function BranchSelect({
  roleCode,
  id,
  error,
  ...props
}: { roleCode: RoleCode | ""; id: string; error?: string | undefined } & React.SelectHTMLAttributes<HTMLSelectElement>) {
  const branches = useQuery({ queryKey: ["reference", "branches"], queryFn: adminApi.branches, staleTime: 5 * 60_000 });
  const companyWide = STAFF_ROLES.find((r) => r.value === roleCode)?.companyWide ?? false;
  return (
    <Field label="Branch" htmlFor={id} error={error} hint={companyWide ? "This role covers all branches" : undefined}>
      <NativeSelect
        id={id}
        disabled={companyWide}
        placeholder={companyWide ? "All branches" : "Select a branch"}
        options={(branches.data ?? []).map((b) => ({ value: b.branch_id, label: `${b.branch_name} (${b.branch_code})` }))}
        {...props}
      />
    </Field>
  );
}

type CreateForm = { full_name: string; email: string; phone: string; role_code: RoleCode | ""; branch_id: string };

function CreateUserDialog({ onClose, onCreated }: { onClose: () => void; onCreated: (user: StaffUserWithPassword) => void }) {
  const form = useForm<CreateForm>({ defaultValues: { full_name: "", email: "", phone: "", role_code: "TRAINER", branch_id: "" } });
  const roleCode = form.watch("role_code");
  const create = useApiMutation(
    (v: CreateForm) =>
      adminApi.createUser({
        full_name: v.full_name,
        email: v.email,
        ...(v.phone ? { phone: v.phone } : {}),
        scopes: [{ role_code: v.role_code as RoleCode, branch_id: v.branch_id ? Number(v.branch_id) : null }],
      }),
    { invalidate: [[...IDS]], onSuccess: onCreated, silentValidation: true, onError: (e) => applyServerErrors(form, e) },
  );
  const errors = form.formState.errors;
  return (
    <FormDialog
      title="Add staff user"
      description="They get a one-time link by WhatsApp (when a phone number is given) to choose their own password. A temporary password is shown only if the link can't be sent."
      submitLabel="Create user"
      onClose={onClose}
      busy={create.isPending}
      onSubmit={form.handleSubmit((v) => create.mutate(v))}
    >
      <Field label="Full name" htmlFor="cu-name" error={errors.full_name?.message}>
        <Input id="cu-name" {...form.register("full_name", { required: "Required" })} />
      </Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Email" htmlFor="cu-email" error={errors.email?.message}>
          <Input id="cu-email" type="email" {...form.register("email", { required: "Required" })} />
        </Field>
        <Field label="Phone (optional)" htmlFor="cu-phone" error={errors.phone?.message}>
          <Input id="cu-phone" type="tel" {...form.register("phone")} />
        </Field>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Role" htmlFor="cu-role" error={errors.role_code?.message} hint={roleHint(roleCode)} className="sm:col-span-2">
          <NativeSelect id="cu-role" options={roleOptions} {...form.register("role_code")} />
        </Field>
        <BranchSelect id="cu-branch" roleCode={roleCode} error={errors.branch_id?.message} {...form.register("branch_id")} />
      </div>
    </FormDialog>
  );
}

/** Revoke one role scope (with `scope`) or deactivate the whole account: both need a reason for the audit log. */
function ReasonDialog({ title, user, scope, unlock, onClose }: { title: string; user: StaffUser; scope?: StaffScope; unlock?: boolean; onClose: () => void }) {
  const form = useForm<{ reason: string }>({ defaultValues: { reason: "" } });
  const done = unlock ? `${user.full_name} can sign in again` : scope ? `${scope.role_name} revoked from ${user.full_name}` : `${user.full_name} deactivated`;
  const save = useApiMutation(
    (v: { reason: string }) =>
      unlock
        ? adminApi.unlockUser(user.user_id, v.reason)
        : scope
          ? adminApi.revokeScope(user.user_id, scope.scope_id, v.reason)
          : adminApi.deactivateUser(user.user_id, v.reason),
    { success: done, invalidate: [[...IDS]], onSuccess: onClose, silentValidation: true, onError: (e) => applyServerErrors(form, e) },
  );
  return (
    <FormDialog
      title={title}
      description={
        unlock
          ? `${user.full_name} was locked after too many wrong passwords. Unlocking lets them try again now.`
          : scope
            ? `${user.full_name} · ${scope.role_name} · ${scope.branch_code ?? "all branches"}`
            : `${user.full_name} can no longer sign in and their sessions end.`
      }
      submitLabel={unlock ? "Unlock" : scope ? "Revoke" : "Deactivate"}
      destructive={!unlock}
      onClose={onClose}
      busy={save.isPending}
      onSubmit={form.handleSubmit((v) => save.mutate(v))}
    >
      <Field label="Reason" htmlFor="reason" error={form.formState.errors.reason?.message}>
        <Input id="reason" {...form.register("reason", { required: "Give a reason for the audit log" })} />
      </Field>
    </FormDialog>
  );
}

const LINK_LABEL: Record<string, string> = { none: "No link yet", valid: "Link active", expired: "Link expired", used: "Activated", revoked: "Link replaced" };

/** Accounts created when people who held two roles were split; the Super Admin or Founder gives each person their link. */
function HandoutSection() {
  const [page, setPage] = useState(1);
  const [secret, setSecret] = useState<{ title: string; handout: SplitHandout } | null>(null);
  const query = useQuery({ queryKey: adminKeys.handouts(page), queryFn: () => adminApi.handouts(page) });
  const issue = useApiMutation((h: SplitHandout) => adminApi.issueHandoutLink(h.handout_id), {
    invalidate: [[...IDS]],
    onSuccess: (h) => setSecret({ title: `Activation link for ${h.full_name}`, handout: h }),
  });
  const handedOut = useApiMutation((h: SplitHandout) => adminApi.markHandedOut(h.handout_id), {
    success: (h) => `${h.full_name} marked as handed out`,
    invalidate: [[...IDS]],
  });
  if (!query.data || query.data.meta.total === 0) return null;
  return (
    <>
      <Section title="Accounts to hand out">
        <p className="mb-3 text-sm text-muted-foreground">
          People who held two roles now have one account per role. Give each new account's one-time activation link to the person, then mark it handed out.
        </p>
        <DataTable
          caption="Accounts created by the role split"
          rows={query.data.data}
          getKey={(h) => h.handout_id}
          cols={[
            {
              h: "Account",
              c: (h) => (
                <>
                  <div className="font-medium">{h.full_name}</div>
                  <div className="text-xs text-muted-foreground">{h.email}</div>
                  <div className="text-xs text-muted-foreground">Split from {h.split_from_email}</div>
                </>
              ),
            },
            { h: "Role", c: (h) => `${h.role_name}${h.branches.length ? ` · ${h.branches.map((b) => b.branch_name).join(", ")}` : " · all branches"}` },
            {
              h: "Link",
              c: (h) => (
                <>
                  <div>{LINK_LABEL[h.link_status] ?? h.link_status}</div>
                  {h.link_status === "valid" && h.link_expires_at && (
                    <div className="text-xs text-muted-foreground">until {istDateTime(h.link_expires_at)}</div>
                  )}
                </>
              ),
            },
            { h: "Handed out", c: (h) => (h.handed_out_at ? `${istDateTime(h.handed_out_at)}${h.handed_out_by ? ` by ${h.handed_out_by}` : ""}` : "Not yet") },
            {
              h: "Actions",
              c: (h) => (
                <div className="flex flex-wrap gap-1.5">
                  {!h.activated && (
                    <ConfirmDialog
                      title={`${h.link_status === "none" ? "Create" : "Create a new"} activation link for ${h.full_name}?`}
                      consequence="The link works once and is shown only now. Any earlier link for this account stops working."
                      confirmLabel="Create link"
                      onConfirm={() => issue.mutateAsync(h).then(() => undefined)}
                    >
                      <Button variant="outline" size="sm" aria-label={`Create activation link for ${h.email}`}>
                        <Send className="size-3.5" /> {h.link_status === "none" ? "Get link" : "New link"}
                      </Button>
                    </ConfirmDialog>
                  )}
                  {!h.handed_out_at && (
                    <Button size="sm" onClick={() => handedOut.mutate(h)} aria-label={`Mark ${h.email} as handed out`}>
                      <UserCheck className="size-3.5" /> Mark handed out
                    </Button>
                  )}
                </div>
              ),
            },
          ]}
        />
        <Pager meta={query.data.meta} onPage={setPage} />
      </Section>
      {secret?.handout.invite_path && (
        <SecretDialog
          title={secret.title}
          description={`Give this link to ${secret.handout.full_name} (${secret.handout.email}). It works once, then they choose their own password. Shown only now.`}
          secrets={[{ label: "Activation link", value: `${window.location.origin}${secret.handout.invite_path}` }]}
          onClose={() => setSecret(null)}
        />
      )}
    </>
  );
}
