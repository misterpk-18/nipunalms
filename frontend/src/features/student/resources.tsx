import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { toast } from "sonner";
import { contentApi, CONTENT_TYPES, accessText, openContentFile, type StudentResource } from "@/api/content";
import { errorMessage } from "@/api/client";
import { DataTable, Note, PageHead, QueryView, StatusBadge } from "@/components/lms/ui";
import { NativeSelect } from "@/components/lms/forms";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useT } from "@/lib/i18n";
import { AccessWindow } from "./access-window";

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

export function Resources() {
  const t = useT();
  const [courseId, setCourseId] = useState("");
  const [contentType, setContentType] = useState("");
  const [text, setText] = useState("");
  const query = useQuery({
    queryKey: ["me", "resources", { courseId, contentType, text }],
    queryFn: () => contentApi.resources({ course_id: courseId, content_type: contentType, q: text }),
  });
  const everything = useQuery({ queryKey: ["me", "resources", "all"], queryFn: () => contentApi.resources() });
  const courses = [...new Map((everything.data ?? []).map((r) => [r.course.course_id, r.course])).values()];

  return (
    <div className="mx-auto max-w-6xl">
      <PageHead title={t("resources")} description="Content Library — released learning materials for your enrolled courses." />
      <AccessWindow focus="Material" />
      <div className="mb-3 grid gap-2 sm:grid-cols-3">
        <NativeSelect
          aria-label="Course"
          value={courseId}
          onChange={(e) => setCourseId(e.target.value)}
          placeholder="All courses"
          options={courses.map((c) => ({ value: c.course_id, label: c.title }))}
        />
        <NativeSelect
          aria-label="Type"
          value={contentType}
          onChange={(e) => setContentType(e.target.value)}
          placeholder="All types"
          options={CONTENT_TYPES.map((c) => ({ value: c, label: c }))}
        />
        <Input aria-label="Search resources" placeholder="Search by title" value={text} onChange={(e) => setText(e.target.value)} />
      </div>
      <QueryView
        query={query}
        isEmpty={(rows) => rows.length === 0}
        empty="No released resources match. New material appears here once your Academic Coordinator releases it."
      >
        {(rows) => (
          <DataTable
            caption="Resources"
            rows={rows}
            getKey={(r) => r.content_item_id}
            cols={[
              { h: "Resource", c: (r) => <span className="font-medium">{r.title}</span> },
              { h: "Type", c: (r) => <StatusBadge tone="info">{r.content_type}</StatusBadge> },
              {
                h: "Used in",
                c: (r) => [r.track ? `${r.track.track_name}` : r.course.course_code, r.topic?.title].filter(Boolean).join(" · "),
              },
              { h: "Access", c: (r) => (r.storage_kind === "Link" ? "External link" : accessText(r.access)) },
              {
                h: "Open",
                c: (r) => (
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" variant="outline" disabled={r.access.state === "Expired"} onClick={() => void open(r)}>
                      Open
                    </Button>
                    {r.download_allowed && r.access.state !== "Expired" && (
                      <Button size="sm" variant="ghost" onClick={() => void download(r)}>
                        Download
                      </Button>
                    )}
                  </div>
                ),
              },
            ]}
          />
        )}
      </QueryView>
      <div className="mt-4">
        <Note>
          One authoritative resource can appear in multiple placements; progress and files are not duplicated. Downloads follow the policy set for each
          resource.
        </Note>
      </div>
    </div>
  );
}
