/** The public "type a certificate number" box: used on /verify and under every answer on /verify/$number. */
import { useState, type FormEvent } from "react";
import { useNavigate } from "@tanstack/react-router";
import { Field } from "@/components/lms/forms";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function VerifyForm({ label = "Certificate number" }: { label?: string }) {
  const navigate = useNavigate();
  const [number, setNumber] = useState("");
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const value = number.trim().toUpperCase();
    if (value) void navigate({ to: "/verify/$number", params: { number: value } });
  };
  return (
    <form onSubmit={submit} className="flex flex-wrap items-end gap-2">
      <Field label={label} htmlFor="verify-number" hint="As printed on the certificate, for example NIT-CERT-2026-000001" className="min-w-0 flex-1">
        <Input id="verify-number" value={number} onChange={(e) => setNumber(e.target.value)} autoComplete="off" spellCheck={false} />
      </Field>
      <Button type="submit" disabled={!number.trim()}>
        Check
      </Button>
    </form>
  );
}
