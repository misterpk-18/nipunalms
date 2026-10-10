/** Class Materials: recordings and files in one place, grouped by course and then by topic (or week). */
import { useState, type ReactNode } from "react";
import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { useNavigate, useSearch } from "@tanstack/react-router";
import { FileText, Link2, PlayCircle } from "lucide-react";
import { toast } from "sonner";
import { contentApi, CONTENT_TYPES, openContentFile, type Playback, type StudentRecording, type StudentResource } from "@/api/content";
import { errorMessage } from "@/api/client";
import { EmptyState } from "@/components/lms/empty-state";
import { NativeSelect } from "@/components/lms/forms";
import { PageHead, PillTabs, QueryView, StatusBadge, StatusNote, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { fmtDate } from "@/features/shared/format";
import { useT } from "@/lib/i18n";
import { AccessLines, AccessRules } from "./access-window";

const TABS = ["recordings", "files"] as const;
type Tab = (typeof TABS)[number];
type T = ReturnType<typeof useT>;

// ---------------------------------------------------------------- grouping

type Group<I> = { key: string; title: string; items: I[] };

/** Items grouped by a key, keeping the order in which each key first appears. */
function groupInOrder<I>(items: I[], keyOf: (item: I) => { key: string; title: string }): Group<I>[] {
  const groups = new Map<string, Group<I>>();
  for (const item of items) {
    const { key, title } = keyOf(item);
    const group = groups.get(key) ?? { key, title, items: [] };
    group.items.push(item);
    groups.set(key, group);
  }
  return [...groups.values()];
}

const istDay = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Kolkata" });

/** The Monday of the IST week of a date-time, as YYYY-MM-DD. */
function weekStart(iso: string): string {
  const day = new Date(`${istDay.format(new Date(iso))}T00:00:00Z`);
  day.setUTCDate(day.getUTCDate() - ((day.getUTCDay() + 6) % 7));
  return day.toISOString().slice(0, 10);
}

type CourseGroup<I> = { course: { course_id: number; course_code: string; title: string }; groups: Group<I>[] };

/** Course, then topic (or week) inside it. Every list arrives newest first, so the order inside each group follows that. */
function byCourse<I extends { course: CourseGroup<I>["course"] }>(items: I[], subgroup: (item: I) => { key: string; title: string }): CourseGroup<I>[] {
  return groupInOrder(items, (item) => ({ key: String(item.course.course_id), title: item.course.title })).map((group) => ({
    course: items.find((i) => String(i.course.course_id) === group.key)!.course,
    groups: groupInOrder(group.items, subgroup),
  }));
}

function CourseSections<I>({ courses, children }: { courses: CourseGroup<I>[]; children: (items: I[]) => ReactNode }) {
  return (
    <div className="space-y-8">
      {courses.map(({ course, groups }) => (
        <section key={course.course_id} aria-label={course.title} className="space-y-4">
          <h2 className="border-b pb-1 text-lg font-semibold">
            {course.course_code} · {course.title}
          </h2>
          {groups.map((group) => (
            <div key={group.key}>
              <h3 className="mb-2 text-sm font-semibold text-muted-foreground">{group.title}</h3>
              {children(group.items)}
            </div>
          ))}
        </section>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------- recordings

function VideoCard({ recording, onWatch }: { recording: StudentRecording; onWatch: (recording: StudentRecording) => void }) {
  const t = useT();
  const ended = recording.access.state === "Expired";
  return (
    <li className="flex flex-col overflow-hidden rounded-xl border bg-card shadow-sm">
      <div className="relative grid aspect-[16/6] place-items-center bg-navy text-navy-foreground" aria-hidden>
        <PlayCircle className="size-10 opacity-90" />
        {recording.duration_minutes ? (
          <span className="absolute bottom-2 right-2 rounded bg-black/60 px-1.5 py-0.5 text-xs text-white">
            {t("unitMinutes", { n: recording.duration_minutes })}
          </span>
        ) : null}
      </div>
      <div className="flex flex-1 flex-col gap-1.5 p-3">
        <h4 className="font-semibold leading-snug">{recording.session.title}</h4>
        <p className="text-xs text-muted-foreground">
          {fmtDate(recording.session.starts_at)} · {recording.session.trainer.full_name}
        </p>
        <div className="flex flex-wrap gap-1.5">
          {ended ? (
            <StatusBadge domain="recording" code="Expired" />
          ) : (
            recording.status !== "Released" && <StatusBadge domain="recording" code={recording.status} />
          )}
          {!recording.download_allowed && recording.playable && !ended && <Tag>{t("streamingOnly")}</Tag>}
        </div>
        {recording.status_note && <p className="text-xs text-muted-foreground">{recording.status_note}</p>}
        <div className="mt-auto pt-2">
          {recording.playable && !ended ? (
            <Button size="sm" className="tap w-full" onClick={() => onWatch(recording)}>
              {t("watch")}
            </Button>
          ) : (
            <p className="text-xs text-muted-foreground">{t("notPlayable")}</p>
          )}
        </div>
      </div>
    </li>
  );
}

function RecordingsTab({ recordings }: { recordings: UseQueryResult<StudentRecording[]> }) {
  const t = useT();
  const [playing, setPlaying] = useState<Playback | null>(null);

  async function watch(recording: StudentRecording) {
    try {
      setPlaying(await contentApi.watch(recording.recording_id));
    } catch (error) {
      toast.error(errorMessage(error));
    }
  }

  return (
    <>
      <AccessLines focus="Recording" />
      <QueryView query={recordings} skeleton="cards" isEmpty={(rows) => rows.length === 0} empty={t("noRecordings")}>
        {(rows) => (
          <CourseSections
            courses={byCourse(rows, (r) =>
              r.topic
                ? { key: `topic-${r.topic.topic_id}`, title: r.topic.title }
                : { key: `week-${weekStart(r.session.starts_at)}`, title: t("weekOf", { date: fmtDate(weekStart(r.session.starts_at)) }) },
            )}
          >
            {(items) => (
              <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
                {items.map((recording) => (
                  <VideoCard key={recording.recording_id} recording={recording} onWatch={(r) => void watch(r)} />
                ))}
              </ul>
            )}
          </CourseSections>
        )}
      </QueryView>
      <Dialog open={playing !== null} onOpenChange={(open) => !open && setPlaying(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{playing?.session_title}</DialogTitle>
            <DialogDescription>{playing?.playback.mode === "stream" ? t("streamingOnly") : t("downloadFile")}</DialogDescription>
          </DialogHeader>
          {playing?.status_note && <StatusNote tone="warning">{playing.status_note}</StatusNote>}
          {playing && !playing.playback.available ? (
            <StatusNote tone="info">{playing.playback.message}</StatusNote>
          ) : (
            <div className="grid aspect-video place-items-center rounded-lg bg-navy text-sm text-navy-foreground">{t("playerPlaceholder")}</div>
          )}
          <p className="text-xs text-muted-foreground">{t("viewSaved")}</p>
        </DialogContent>
      </Dialog>
    </>
  );
}

// ---------------------------------------------------------------- files

async function open(resource: StudentResource) {
  try {
    const opened = await contentApi.open(resource.content_item_id);
    if (opened.storage_kind === "Link" && opened.url) window.open(opened.url, "_blank", "noopener,noreferrer");
    else await openContentFile(resource.content_item_id, opened.original_filename, !opened.inline);
  } catch (error) {
    toast.error(errorMessage(error));
  }
}

async function download(resource: StudentResource) {
  try {
    await openContentFile(resource.content_item_id, resource.original_filename, true);
  } catch (error) {
    toast.error(errorMessage(error));
  }
}

function FileRow({ resource }: { resource: StudentResource }) {
  const t = useT();
  const ended = resource.access.state === "Expired";
  const Icon = resource.storage_kind === "Link" ? Link2 : FileText;
  return (
    <li className="flex flex-wrap items-center gap-3 rounded-xl border bg-card p-3 shadow-sm">
      <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-primary/10 text-primary" aria-hidden>
        <Icon className="size-5" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <span className="font-medium">{resource.title}</span>
          <Tag tone="info">{resource.content_type}</Tag>
          {resource.storage_kind === "Link" && <Tag>{t("externalLink")}</Tag>}
          {ended && <StatusBadge domain="recording" code="Expired" />}
        </div>
        {resource.description && <p className="mt-0.5 text-sm text-muted-foreground">{resource.description}</p>}
      </div>
      <div className="flex shrink-0 flex-wrap gap-2">
        <Button size="sm" variant="outline" className="tap" disabled={ended} onClick={() => void open(resource)}>
          {t("openFile")}
        </Button>
        {resource.download_allowed && !ended && resource.storage_kind === "File" && (
          <Button size="sm" variant="ghost" className="tap" onClick={() => void download(resource)}>
            {t("downloadFile")}
          </Button>
        )}
      </div>
    </li>
  );
}

function FilesTab({ files }: { files: UseQueryResult<StudentResource[]> }) {
  const t = useT();
  const [courseId, setCourseId] = useState("");
  const [contentType, setContentType] = useState("");
  const [text, setText] = useState("");
  return (
    <>
      <AccessLines focus="Material" />
      <QueryView query={files} skeleton="cards" isEmpty={(rows) => rows.length === 0} empty={t("noFiles")}>
        {(all) => {
          const courses = [...new Map(all.map((r) => [r.course.course_id, r.course])).values()];
          const needle = text.trim().toLowerCase();
          const rows = all.filter(
            (r) =>
              (!courseId || String(r.course.course_id) === courseId) &&
              (!contentType || r.content_type === contentType) &&
              (!needle || r.title.toLowerCase().includes(needle)),
          );
          return (
            <>
              <div className="mb-4 grid gap-2 sm:grid-cols-3">
                <NativeSelect
                  aria-label={t("filterCourse")}
                  value={courseId}
                  onChange={(e) => setCourseId(e.target.value)}
                  placeholder={t("allCourses")}
                  options={courses.map((c) => ({ value: String(c.course_id), label: c.title }))}
                />
                <NativeSelect
                  aria-label={t("filterType")}
                  value={contentType}
                  onChange={(e) => setContentType(e.target.value)}
                  placeholder={t("allTypes")}
                  options={CONTENT_TYPES.map((c) => ({ value: c, label: c }))}
                />
                <Input aria-label={t("searchFiles")} placeholder={t("searchFiles")} value={text} onChange={(e) => setText(e.target.value)} />
              </div>
              {rows.length === 0 ? (
                <EmptyState reason={t("noFiles")} />
              ) : (
                <CourseSections courses={byCourse(rows, (r) => groupOfFile(r, t))}>
                  {(items) => (
                    <ul className="space-y-2">
                      {items.map((resource) => (
                        <FileRow key={resource.content_item_id} resource={resource} />
                      ))}
                    </ul>
                  )}
                </CourseSections>
              )}
            </>
          );
        }}
      </QueryView>
    </>
  );
}

/** A file sits under its topic, else its module, else "General". */
function groupOfFile(r: StudentResource, t: T): { key: string; title: string } {
  if (r.topic) return { key: `topic-${r.topic.topic_id}`, title: r.topic.title };
  if (r.module) return { key: `module-${r.module.module_id}`, title: r.module.title };
  return { key: "general", title: t("generalFiles") };
}

// ---------------------------------------------------------------- the screen

export function Materials() {
  const t = useT();
  const { tab = "recordings" } = useSearch({ from: "/materials" });
  const navigate = useNavigate({ from: "/materials" });
  const recordings = useQuery({ queryKey: ["me", "recordings"], queryFn: () => contentApi.recordings() });
  const files = useQuery({ queryKey: ["me", "resources", "all"], queryFn: () => contentApi.resources() });
  const counts: Partial<Record<Tab, number>> = { recordings: recordings.data?.length, files: files.data?.length };
  const labels: Record<Tab, string> = { recordings: t("recordings"), files: t("tabFiles") };
  return (
    <div className="mx-auto max-w-6xl">
      <PageHead title={t("classMaterials")} description={t("materialsHelp")} />
      <PillTabs
        tabs={TABS}
        value={tab}
        label={t("materialsViews")}
        labels={labels}
        counts={counts}
        onChange={(next) => void navigate({ search: next === "recordings" ? {} : { tab: next }, replace: true })}
      />
      {tab === "recordings" ? <RecordingsTab recordings={recordings} /> : <FilesTab files={files} />}
      <div className="mt-8">
        <AccessRules />
      </div>
    </div>
  );
}
