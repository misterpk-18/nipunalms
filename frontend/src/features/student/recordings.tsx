import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { contentApi, accessText, formatDateTime, type Playback, type StudentRecording } from "@/api/content";
import { errorMessage } from "@/api/client";
import { DataTable, Note, PageHead, QueryView, StatusBadge, StatusNote } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useT } from "@/lib/i18n";
import { AccessWindow } from "./access-window";

export function Recordings() {
  const t = useT();
  const query = useQuery({ queryKey: ["me", "recordings"], queryFn: () => contentApi.recordings() });
  const [playing, setPlaying] = useState<Playback | null>(null);

  async function watch(recording: StudentRecording) {
    try {
      setPlaying(await contentApi.watch(recording.recording_id));
    } catch (error) {
      toast.error(errorMessage(error));
    }
  }

  return (
    <div className="mx-auto max-w-6xl">
      <PageHead title={t("recordings")} description="Recordings of the classes of your batches." />
      <AccessWindow focus="Recording" />
      <QueryView query={query} isEmpty={(rows) => rows.length === 0} empty="No recordings yet. Recordings appear here after a class is delivered and released.">
        {(rows) => (
          <DataTable
            caption="Recordings"
            rows={rows}
            getKey={(r) => r.recording_id}
            cols={[
              { h: "Course / track", c: (r) => [r.course.course_code, r.track?.track_name].filter(Boolean).join(" · ") },
              {
                h: "Session",
                c: (r) => (
                  <>
                    <div className="font-medium">{r.session.title}</div>
                    <div className="text-xs text-muted-foreground">
                      {formatDateTime(r.session.starts_at)} · {r.session.trainer.full_name}
                    </div>
                    {r.status_note && <div className="text-xs text-muted-foreground">{r.status_note}</div>}
                  </>
                ),
              },
              { h: "Status", c: (r) => <StatusBadge>{r.status}</StatusBadge> },
              { h: "Access until", c: (r) => accessText(r.access) },
              { h: "Download", c: (r) => (r.download_allowed ? "Download permitted" : "Streaming only — download not permitted") },
              {
                h: "Action",
                c: (r) =>
                  r.playable ? (
                    <Button size="sm" onClick={() => void watch(r)}>
                      {t("watch")}
                    </Button>
                  ) : (
                    <span className="text-xs text-muted-foreground">Not playable</span>
                  ),
              },
            ]}
          />
        )}
      </QueryView>
      <div className="mt-4">
        <Note>Playback uses controlled viewing through the LMS. Google Drive and Meet are not connected yet, so nothing is played from Drive.</Note>
      </div>
      <Dialog open={playing !== null} onOpenChange={(open) => !open && setPlaying(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{playing?.session_title}</DialogTitle>
            <DialogDescription>
              {playing?.recording_code} · {playing?.playback.mode === "stream" ? "Streaming only" : "Download permitted"}
            </DialogDescription>
          </DialogHeader>
          {playing?.status_note && <StatusNote state="Partial Data">{playing.status_note}</StatusNote>}
          {playing && !playing.playback.available ? (
            <StatusNote state="Integration Unavailable">{playing.playback.message}</StatusNote>
          ) : (
            <div className="grid aspect-video place-items-center rounded-lg bg-navy text-sm text-navy-foreground">Player</div>
          )}
          <p className="text-xs text-muted-foreground">Your view has been recorded in your learning activity.</p>
        </DialogContent>
      </Dialog>
    </div>
  );
}
