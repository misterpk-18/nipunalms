import { useT } from "@/lib/i18n";
import { Assistant } from "@/features/shared/assistant";

export function AskNipuna() {
  const t = useT();
  return <Assistant title={t("askNipuna")} />;
}
