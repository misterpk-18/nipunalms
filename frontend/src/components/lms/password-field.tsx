import { useState, type ComponentProps } from "react";
import { Eye, EyeOff } from "lucide-react";
import { Input } from "@/components/ui/input";
import { useT } from "@/lib/i18n";

/** Password input with a show / hide button. */
export function PasswordField(props: Omit<ComponentProps<typeof Input>, "type">) {
  const t = useT();
  const [shown, setShown] = useState(false);
  return (
    <div className="relative">
      <Input {...props} type={shown ? "text" : "password"} className="tap pr-11" />
      <button
        type="button"
        onClick={() => setShown((s) => !s)}
        aria-label={shown ? t("hidePassword") : t("showPassword")}
        className="tap absolute inset-y-0 right-0 grid place-items-center text-muted-foreground hover:text-foreground"
      >
        {shown ? <EyeOff className="size-4" aria-hidden /> : <Eye className="size-4" aria-hidden />}
      </button>
    </div>
  );
}
