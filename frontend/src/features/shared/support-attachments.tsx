/** Files on a support message: the links under a message, and the picker that adds up to three files to a message being written. */
import { useRef } from "react";
import { FileText, Paperclip, X } from "lucide-react";
import { toast } from "sonner";
import { ATTACHMENT_ACCEPT, ATTACHMENT_MAX_BYTES, ATTACHMENT_MAX_FILES, supportApi, type SupportAttachment } from "@/api/support";
import { Button } from "@/components/ui/button";
import { useApiMutation } from "@/lib/mutation";

export const fileSize = (bytes: number) => (bytes >= 1024 * 1024 ? `${(bytes / (1024 * 1024)).toFixed(1)} MB` : `${Math.max(1, Math.round(bytes / 1024))} KB`);

/** The files of one message. Each is a button that downloads it (the API checks who may). */
export function AttachmentLinks({ attachments, downloadLabel = "Download" }: { attachments: SupportAttachment[]; downloadLabel?: string }) {
  const download = useApiMutation((attachment: SupportAttachment) => supportApi.downloadAttachment(attachment));
  if (attachments.length === 0) return null;
  return (
    <ul className="mt-2 flex flex-wrap gap-2">
      {attachments.map((a) => (
        <li key={a.attachment_id}>
          <button
            type="button"
            onClick={() => download.mutate(a)}
            aria-label={`${downloadLabel}: ${a.filename}`}
            className="tap inline-flex max-w-full items-center gap-1.5 rounded-lg border bg-background px-2.5 py-1 text-xs hover:bg-accent"
          >
            <FileText className="size-3.5 shrink-0" aria-hidden />
            <span className="truncate">{a.filename}</span>
            <span className="shrink-0 text-muted-foreground">{fileSize(a.size_bytes)}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}

/**
 * Chosen files, with a remove button each. The type and size limits are checked here too (the API checks them again), so a wrong file
 * is refused before anything is sent. `text` holds the words so a student screen can pass the translation.
 */
export function FilePicker({
  files,
  onChange,
  text,
  inputId,
}: {
  files: File[];
  onChange: (files: File[]) => void;
  text: { add: string; hint: string; tooBig: (name: string) => string; wrongType: (name: string) => string; tooMany: string; remove: (name: string) => string };
  inputId: string;
}) {
  const input = useRef<HTMLInputElement>(null);
  const allowed = ATTACHMENT_ACCEPT.split(",");

  function add(chosen: FileList | null) {
    const next = [...files];
    for (const file of Array.from(chosen ?? [])) {
      const extension = `.${file.name.split(".").pop()?.toLowerCase() ?? ""}`;
      if (!allowed.includes(extension)) toast.error(text.wrongType(file.name));
      else if (file.size > ATTACHMENT_MAX_BYTES) toast.error(text.tooBig(file.name));
      else if (next.length >= ATTACHMENT_MAX_FILES) {
        toast.error(text.tooMany);
        break;
      } else next.push(file);
    }
    onChange(next);
    if (input.current) input.current.value = "";
  }

  return (
    <div className="space-y-2">
      <input id={inputId} ref={input} type="file" multiple accept={ATTACHMENT_ACCEPT} className="sr-only" onChange={(e) => add(e.target.files)} />
      <div className="flex flex-wrap items-center gap-2">
        <Button type="button" variant="outline" size="sm" onClick={() => input.current?.click()} disabled={files.length >= ATTACHMENT_MAX_FILES}>
          <Paperclip aria-hidden /> {text.add}
        </Button>
        <span className="text-xs text-muted-foreground">{text.hint}</span>
      </div>
      {files.length > 0 && (
        <ul className="flex flex-wrap gap-2">
          {files.map((file, index) => (
            <li key={`${file.name}-${index}`} className="inline-flex max-w-full items-center gap-1.5 rounded-lg border bg-background px-2.5 py-1 text-xs">
              <FileText className="size-3.5 shrink-0" aria-hidden />
              <span className="truncate">{file.name}</span>
              <span className="shrink-0 text-muted-foreground">{fileSize(file.size)}</span>
              <button
                type="button"
                onClick={() => onChange(files.filter((_, i) => i !== index))}
                aria-label={text.remove(file.name)}
                className="rounded p-0.5 hover:bg-muted"
              >
                <X className="size-3.5" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
