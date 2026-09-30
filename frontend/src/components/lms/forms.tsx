/**
 * Form helpers. Forms use react-hook-form; server validation errors (`error.details`) are mapped onto fields
 * with `applyServerErrors`. Selects are native <select> elements styled like inputs — simple to register,
 * accessible, and easy to drive in Playwright.
 */
import { forwardRef, type ReactNode, type SelectHTMLAttributes } from "react";
import { get, type FieldValues, type Path, type UseFormReturn } from "react-hook-form";
import { toast } from "sonner";
import { ApiError } from "@/api/client";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

type FieldProps = {
  label: string;
  error?: string | undefined;
  hint?: ReactNode;
  children: ReactNode;
  className?: string;
  htmlFor?: string;
};

export function Field(props: FieldProps) {
  const { label, error, hint, children, className, htmlFor } = props;
  // `data-shows-errors` marks fields that render an error message, so applyServerErrors knows which inputs can show one.
  return (
    <div className={cn("space-y-1.5", className)} data-field="" data-shows-errors={"error" in props ? "" : undefined}>
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
      {hint && !error && <p className="text-xs text-muted-foreground">{hint}</p>}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  );
}

/** True when `name` is registered, its input is on screen, and it sits in a <Field> that renders errors. */
function showsError<T extends FieldValues>(form: UseFormReturn<T>, name: string): boolean {
  if (!form.control._names.mount.has(name)) return false;
  const f = (get(form.control._fields, name) as { _f?: { ref?: unknown; refs?: unknown[] } } | undefined)?._f;
  const el = [f?.ref, ...(f?.refs ?? [])].find((r): r is Element => r instanceof Element);
  return !!el?.isConnected && !!el.closest("[data-field]")?.hasAttribute("data-shows-errors");
}

/**
 * Copies `{ details: { field: [msg] } }` from a 400 onto the form's fields; returns true when anything was
 * mapped. Errors for fields that can't display them (not in this dialog, hidden, or in a <Field> without an
 * `error` prop) are toasted instead, so a rejected submit is never silent.
 */
export function applyServerErrors<T extends FieldValues>(form: UseFormReturn<T>, error: unknown): boolean {
  if (!(error instanceof ApiError) || !error.details) return false;
  let mapped = false;
  const unmapped: string[] = [];
  for (const [field, messages] of Object.entries(error.details)) {
    const message = Array.isArray(messages) ? messages.join(", ") : String(messages);
    if (showsError(form, field)) {
      form.setError(field as Path<T>, { type: "server", message });
      mapped = true;
    } else {
      unmapped.push(message);
    }
  }
  if (unmapped.length) toast.error(error.message, { description: unmapped.join(" · ") });
  return mapped;
}

export const selectClass =
  "flex h-10 w-full rounded-[8px] border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50";

type NativeSelectProps = SelectHTMLAttributes<HTMLSelectElement> & { placeholder?: string };

export const NativeSelect = forwardRef<HTMLSelectElement, NativeSelectProps & { options: { value: string | number; label: string }[] }>(function NativeSelect(
  { options, placeholder, className, ...props },
  ref,
) {
  return (
    <select ref={ref} className={cn(selectClass, className)} {...props}>
      {placeholder !== undefined && <option value="">{placeholder}</option>}
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
});

/** Turn "" into null and numeric strings into numbers for API bodies. */
export function cleanBody<T extends Record<string, unknown>>(values: T, numeric: (keyof T)[] = []): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(values)) {
    if (value === "" || value === undefined) continue;
    out[key] = numeric.includes(key as keyof T) && value !== null ? Number(value) : value;
  }
  return out;
}
