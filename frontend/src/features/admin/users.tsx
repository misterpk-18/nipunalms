import { useState } from "react";
import { useForm } from "react-hook-form";
import { useQuery } from "@tanstack/react-query";
import { KeyRound, Plus, UserCheck, UserMinus, X } from "lucide-react";
import { adminApi, adminKeys, type StaffScope, type StaffUser, type StaffUserWithPassword, type UserFilters } from "@/api/admin";
import type { RoleCode } from "@/api/types";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field, NativeSelect, applyServerErrors } from "@/components/lms/forms";
import { ConfirmAction, DataTable, Note, PageHead, QueryView, Section, StatusBadge } from "@/components/lms/ui";
import { useApiMutation } from "@/lib/mutation";
import { FilterField, FormDialog, Pager, SecretDialog } from "./shared";
import { istDateTime, useCanAdminister } from "./format";

const STAFF_ROLES: { value: RoleCode; label: string; companyWide: boolean }[] = [
  { value: "TRAINER", label: "Trainer", companyWide: false },
  { value: "ACADEMIC_COORDINATOR", label: "Academic Coordinator", companyWide: false },
  { value: "BRANCH_MANAGER", label: "Branch Manager", companyWide: false },
  { value: "SUPER_ADMIN", label: "Super Admin", companyWide: true },
  { value: "FOUNDER_CEO", label: "Founder / CEO", companyWide: true },
];

type Action =
  { kind: "create" } | { kind: "add-role"; user: StaffUser } | { kind: "revoke"; user: StaffUser; scope: StaffScope } | { kind: "deactivate"; user: StaffUser };

const IDS = adminKeys.usersAll;

/** Users & Access: staff accounts and their role scopes. Students are created by the CRM, never here. */
export function AdminUsers() {
  const canEdit = useCanAdminister();
  const [filters, setFilters] = useState<UserFilters>({ is_active: "true" });
  const [action, setAction] = useState<Action | null>(null);
  const [secret, setSecret] = useState<{ title: string; user: StaffUserWithPassword } | null>(null);
  const query = useQuery({ queryKey: adminKeys.users(filters), queryFn: () => adminApi.users(filters) });

  const reactivate = useApiMutation((user: StaffUser) => adminApi.reactivateUser(user.user_id), {
    success: (u) => `${u.full_name} reactivated`,
    invalidate: [[...IDS]],
  });
  const reset = useApiMutation((user: StaffUser) => adminApi.resetPassword(user.user_id), {
    invalidate: [[...IDS]],
    onSuccess: (user) => setSecret({ title: `Password reset for ${user.full_name}`, user }),
  });

  return (
    <>
      <PageHead
        title="Users & Access"
        description="Staff accounts and role scopes by branch. Students are created by the CRM and administered under Student Accounts."
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
                value={filters.is_active ?? ""}
                options={[
                  { value: "true", label: "Active" },
                  { value: "false", label: "Deactivated" },
                ]}
                onChange={(e) => setFilters({ ...filters, is_active: e.target.value, page: 1 })}
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
                          <StatusBadge tone={u.is_active ? "success" : "neutral"}>{u.is_active ? "Active" : "Deactivated"}</StatusBadge>
                          {u.must_change_password && <StatusBadge tone="warning">Must change password</StatusBadge>}
                          {u.is_locked && <StatusBadge tone="danger">Locked</StatusBadge>}
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
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => setAction({ kind: "add-role", user: u })}
                                  aria-label={`Add role to ${u.full_name}`}
                                >
                                  <Plus className="size-3.5" /> Role
                                </Button>
                                <ConfirmAction
                                  title={`Reset password for ${u.full_name}?`}
                                  description="A new temporary password is shown once, every session ends and they must change it at next sign-in."
                                  confirmLabel="Reset password"
                                  onConfirm={() => reset.mutateAsync(u).then(() => undefined)}
                                >
                                  <Button variant="outline" size="sm" aria-label={`Reset password for ${u.full_name}`}>
                                    <KeyRound className="size-3.5" /> Reset
                                  </Button>
                                </ConfirmAction>
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
          Role changes, password resets and deactivation ask for your password again and are written to the audit log. Temporary access lasts at most 7 days.
        </Note>
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
      {action?.kind === "add-role" && <AddRoleDialog user={action.user} onClose={() => setAction(null)} />}
      {action?.kind === "revoke" && (
        <ReasonDialog title={`Revoke ${action.scope.role_name}`} user={action.user} scope={action.scope} onClose={() => setAction(null)} />
      )}
      {action?.kind === "deactivate" && <ReasonDialog title="Deactivate account" user={action.user} onClose={() => setAction(null)} />}
      {secret && (
        <SecretDialog
          title={secret.title}
          description={`Give ${secret.user.email} this temporary password now. It is shown once and cannot be retrieved; they must change it at first sign-in.`}
          label="Temporary password"
          value={secret.user.temporary_password}
          onClose={() => setSecret(null)}
        />
      )}
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
      description="A temporary password is generated and shown once; the user must change it at first sign-in."
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
        <Field label="Role" htmlFor="cu-role" error={errors.role_code?.message}>
          <NativeSelect id="cu-role" options={STAFF_ROLES.map((r) => ({ value: r.value, label: r.label }))} {...form.register("role_code")} />
        </Field>
        <BranchSelect id="cu-branch" roleCode={roleCode} error={errors.branch_id?.message} {...form.register("branch_id")} />
      </div>
    </FormDialog>
  );
}

type RoleForm = { role_code: RoleCode; branch_id: string; expires_at: string };

function AddRoleDialog({ user, onClose }: { user: StaffUser; onClose: () => void }) {
  const form = useForm<RoleForm>({ defaultValues: { role_code: "ACADEMIC_COORDINATOR", branch_id: "", expires_at: "" } });
  const roleCode = form.watch("role_code");
  const grant = useApiMutation(
    (v: RoleForm) =>
      adminApi.grantScope(user.user_id, {
        role_code: v.role_code,
        branch_id: v.branch_id ? Number(v.branch_id) : null,
        expires_at: v.expires_at ? new Date(v.expires_at).toISOString() : null,
      }),
    {
      success: `Role added for ${user.full_name}`,
      invalidate: [[...IDS]],
      onSuccess: onClose,
      silentValidation: true,
      onError: (e) => applyServerErrors(form, e),
    },
  );
  const errors = form.formState.errors;
  return (
    <FormDialog
      title={`Add role for ${user.full_name}`}
      submitLabel="Add role"
      onClose={onClose}
      busy={grant.isPending}
      onSubmit={form.handleSubmit((v) => grant.mutate(v))}
    >
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Role" htmlFor="ar-role" error={errors.role_code?.message}>
          <NativeSelect id="ar-role" options={STAFF_ROLES.map((r) => ({ value: r.value, label: r.label }))} {...form.register("role_code")} />
        </Field>
        <BranchSelect id="ar-branch" roleCode={roleCode} error={errors.branch_id?.message} {...form.register("branch_id")} />
      </div>
      <Field
        label="Temporary access until (optional)"
        htmlFor="ar-expires"
        error={errors.expires_at?.message}
        hint="Leave empty for standing access; temporary access is limited to 7 days"
      >
        <Input id="ar-expires" type="datetime-local" {...form.register("expires_at")} />
      </Field>
    </FormDialog>
  );
}

/** Revoke one role scope (with `scope`) or deactivate the whole account: both need a reason for the audit log. */
function ReasonDialog({ title, user, scope, onClose }: { title: string; user: StaffUser; scope?: StaffScope; onClose: () => void }) {
  const form = useForm<{ reason: string }>({ defaultValues: { reason: "" } });
  const done = scope ? `${scope.role_name} revoked from ${user.full_name}` : `${user.full_name} deactivated`;
  const save = useApiMutation(
    (v: { reason: string }) => (scope ? adminApi.revokeScope(user.user_id, scope.scope_id, v.reason) : adminApi.deactivateUser(user.user_id, v.reason)),
    { success: done, invalidate: [[...IDS]], onSuccess: onClose, silentValidation: true, onError: (e) => applyServerErrors(form, e) },
  );
  return (
    <FormDialog
      title={title}
      description={
        scope
          ? `${user.full_name} · ${scope.role_name} · ${scope.branch_code ?? "all branches"}`
          : `${user.full_name} can no longer sign in and their sessions end.`
      }
      submitLabel={scope ? "Revoke" : "Deactivate"}
      destructive
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
