import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { assessmentsApi, batchesForAuthoring, QUESTION_TYPES, type Question, type QuestionType } from "@/api/assessments";
import { Field, NativeSelect } from "@/components/lms/forms";
import { DataTable, PillTabs, QueryView, StatusBadge } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useApiMutation } from "@/lib/mutation";

const CHOICE = ["Single choice", "Multiple choice"];
const KEYS = ["A", "B", "C", "D"];
const REFRESH = [["questions"]];

/** The key block of a question form: what the correct answer looks like depends on the type. */
function AnswerKey({ type, state, set }: { type: QuestionType; state: KeyState; set: (patch: Partial<KeyState>) => void }) {
  if (CHOICE.includes(type)) {
    return (
      <div className="space-y-2">
        <p className="text-sm font-medium">Options (tick the correct {type === "Single choice" ? "one" : "ones"})</p>
        {KEYS.map((key, i) => (
          <div key={key} className="flex items-center gap-2">
            <input
              type={type === "Single choice" ? "radio" : "checkbox"}
              name="correct"
              aria-label={`Option ${key} is correct`}
              checked={state.correct.includes(key)}
              onChange={(e) =>
                set({ correct: type === "Single choice" ? [key] : e.target.checked ? [...state.correct, key] : state.correct.filter((k) => k !== key) })
              }
            />
            <Input
              aria-label={`Option ${key}`}
              value={state.options[i] ?? ""}
              onChange={(e) => set({ options: state.options.map((o, j) => (j === i ? e.target.value : o)) })}
              placeholder={`Option ${key}`}
            />
          </div>
        ))}
      </div>
    );
  }
  if (type === "True / False")
    return (
      <div className="flex gap-4 text-sm">
        {["true", "false"].map((v) => (
          <label key={v} className="flex items-center gap-1">
            <input type="radio" name="tf" checked={state.truth === v} onChange={() => set({ truth: v })} /> {v === "true" ? "True" : "False"} is correct
          </label>
        ))}
      </div>
    );
  if (type === "Numeric")
    return (
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Correct value" htmlFor="qk-value">
          <Input id="qk-value" inputMode="decimal" value={state.value} onChange={(e) => set({ value: e.target.value })} />
        </Field>
        <Field label="Tolerance" htmlFor="qk-tol">
          <Input id="qk-tol" inputMode="decimal" value={state.tolerance} onChange={(e) => set({ tolerance: e.target.value })} />
        </Field>
      </div>
    );
  if (type === "Short answer" || type === "Output prediction")
    return (
      <Field label="Accepted answers (one per line)" htmlFor="qk-variants">
        <Textarea id="qk-variants" rows={3} value={state.variants} onChange={(e) => set({ variants: e.target.value })} />
      </Field>
    );
  return (
    <Field label="Rubric for the grader" htmlFor="qk-rubric">
      <Textarea id="qk-rubric" rows={3} value={state.rubric} onChange={(e) => set({ rubric: e.target.value })} />
    </Field>
  );
}

type KeyState = { options: string[]; correct: string[]; truth: string; value: string; tolerance: string; variants: string; rubric: string };
const EMPTY_KEY: KeyState = { options: ["", "", "", ""], correct: [], truth: "true", value: "", tolerance: "0", variants: "", rubric: "" };

function buildKey(type: QuestionType, s: KeyState): { options: { key: string; text: string }[]; answer_key: Record<string, unknown> } {
  const options = KEYS.map((key, i) => ({ key, text: s.options[i]?.trim() ?? "" })).filter((o) => o.text);
  if (type === "Single choice") return { options, answer_key: { option: s.correct[0] } };
  if (type === "Multiple choice") return { options, answer_key: { options: s.correct } };
  if (type === "True / False") return { options: [], answer_key: { value: s.truth === "true" } };
  if (type === "Numeric") return { options: [], answer_key: { value: Number(s.value), tolerance: Number(s.tolerance || 0) } };
  if (type === "Short answer" || type === "Output prediction")
    return {
      options: [],
      answer_key: {
        variants: s.variants
          .split("\n")
          .map((v) => v.trim())
          .filter(Boolean),
      },
    };
  return { options: [], answer_key: { rubric: s.rubric } };
}

function NewQuestionDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const batches = useQuery({ queryKey: ["batches", "authoring"], queryFn: batchesForAuthoring, enabled: open });
  const [courseId, setCourseId] = useState("");
  const [topicId, setTopicId] = useState("");
  const [type, setType] = useState<QuestionType>("Single choice");
  const [stem, setStem] = useState("");
  const [marks, setMarks] = useState("1");
  const [difficulty, setDifficulty] = useState("Medium");
  const [tags, setTags] = useState("");
  const [key, setKey] = useState<KeyState>(EMPTY_KEY);
  const courses = [...new Map((batches.data?.data ?? []).map((b) => [b.course.course_id, b.course])).values()];
  const batchOfCourse = (batches.data?.data ?? []).find((b) => String(b.course.course_id) === courseId);
  const topics = useQuery({
    queryKey: ["curriculum-options", batchOfCourse?.batch_id],
    queryFn: () => assessmentsApi.curriculum(batchOfCourse!.batch_id),
    enabled: open && !!batchOfCourse,
  });

  const create = useApiMutation(
    () =>
      assessmentsApi.createQuestion({
        course_id: Number(courseId),
        topic_id: topicId ? Number(topicId) : null,
        question_type: type,
        stem,
        marks: Number(marks),
        difficulty,
        tags: tags
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
        ...buildKey(type, key),
      }),
    {
      success: (q) => `${q.question_code} saved as a draft`,
      invalidate: REFRESH,
      onSuccess: () => {
        onOpenChange(false);
        setStem("");
        setKey(EMPTY_KEY);
      },
    },
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>New question</DialogTitle>
          <DialogDescription>Saved as a draft; the Academic Coordinator approves it before it can go in a test.</DialogDescription>
        </DialogHeader>
        <div className="space-y-3">
          <Field label="Course" htmlFor="q-course">
            <NativeSelect
              id="q-course"
              value={courseId}
              onChange={(e) => {
                setCourseId(e.target.value);
                setTopicId("");
              }}
              placeholder="Select a course"
              options={courses.map((c) => ({ value: c.course_id, label: c.title }))}
            />
          </Field>
          <Field label="Topic" htmlFor="q-topic">
            <NativeSelect
              id="q-topic"
              value={topicId}
              onChange={(e) => setTopicId(e.target.value)}
              placeholder="Not linked to a topic"
              options={(topics.data ?? []).flatMap((m) => m.topics.map((t) => ({ value: t.topic_id, label: `${m.title} → ${t.title}` })))}
            />
          </Field>
          <Field label="Type" htmlFor="q-type">
            <NativeSelect
              id="q-type"
              value={type}
              onChange={(e) => setType(e.target.value as QuestionType)}
              options={QUESTION_TYPES.map((t) => ({ value: t, label: t }))}
            />
          </Field>
          <Field label="Question" htmlFor="q-stem">
            <Textarea id="q-stem" rows={3} value={stem} onChange={(e) => setStem(e.target.value)} />
          </Field>
          <AnswerKey type={type} state={key} set={(patch) => setKey((prev) => ({ ...prev, ...patch }))} />
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Marks" htmlFor="q-marks">
              <Input id="q-marks" inputMode="decimal" value={marks} onChange={(e) => setMarks(e.target.value)} />
            </Field>
            <Field label="Difficulty" htmlFor="q-diff">
              <NativeSelect
                id="q-diff"
                value={difficulty}
                onChange={(e) => setDifficulty(e.target.value)}
                options={["Easy", "Medium", "Hard"].map((d) => ({ value: d, label: d }))}
              />
            </Field>
            <Field label="Tags (comma separated)" htmlFor="q-tags">
              <Input id="q-tags" value={tags} onChange={(e) => setTags(e.target.value)} />
            </Field>
          </div>
        </div>
        <DialogFooter>
          <Button disabled={!courseId || !stem || create.isPending} onClick={() => create.mutate(undefined)}>
            Save draft
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

const STATUS_TABS = ["All", "Draft", "Approved", "Retired"] as const;

/** The bank of the user's branch(es). `canApprove` shows the Academic Coordinator's approve / retire actions. */
export function QuestionBank({ canApprove = false, initialStatus = "All" }: { canApprove?: boolean; initialStatus?: (typeof STATUS_TABS)[number] }) {
  const [status, setStatus] = useState<(typeof STATUS_TABS)[number]>(initialStatus);
  const [creating, setCreating] = useState(false);
  const query = useQuery({ queryKey: ["questions", "list", status], queryFn: () => assessmentsApi.questions(status === "All" ? {} : { status }) });
  const approve = useApiMutation((q: Question) => assessmentsApi.approveQuestion(q.question_id), { success: "Question approved", invalidate: REFRESH });
  const retire = useApiMutation((q: Question) => assessmentsApi.retireQuestion(q.question_id), { success: "Question retired", invalidate: REFRESH });
  const revise = useApiMutation((q: Question) => assessmentsApi.newVersion(q.question_id), { success: "New draft version created", invalidate: REFRESH });

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <PillTabs tabs={STATUS_TABS} value={status} onChange={setStatus} label="Question status" />
        {!canApprove && <Button onClick={() => setCreating(true)}>New question</Button>}
      </div>
      <QueryView query={query} isEmpty={(p) => p.data.length === 0} empty="No questions in this view.">
        {(page) => (
          <DataTable
            caption="Question bank"
            rows={page.data}
            getKey={(q) => q.question_id}
            cols={[
              {
                h: "Code",
                c: (q) => (
                  <span className="font-mono text-xs">
                    {q.question_code} v{q.version}
                  </span>
                ),
              },
              { h: "Question", c: (q) => <span className="whitespace-pre-wrap">{q.stem}</span> },
              { h: "Type", c: (q) => <StatusBadge tone="info">{q.question_type}</StatusBadge> },
              { h: "Topic", c: (q) => q.topic?.title ?? "—" },
              { h: "Marks", c: (q) => `${q.marks} · ${q.difficulty}` },
              { h: "Status", c: (q) => <StatusBadge>{q.status}</StatusBadge> },
              {
                h: "Actions",
                c: (q) => (
                  <div className="flex flex-wrap gap-2">
                    {canApprove && q.status === "Draft" && (
                      <Button size="sm" onClick={() => approve.mutate(q)}>
                        Approve
                      </Button>
                    )}
                    {canApprove && q.status !== "Retired" && (
                      <Button size="sm" variant="outline" onClick={() => retire.mutate(q)}>
                        Retire
                      </Button>
                    )}
                    {!canApprove && q.status !== "Draft" && (
                      <Button size="sm" variant="outline" onClick={() => revise.mutate(q)}>
                        New version
                      </Button>
                    )}
                  </div>
                ),
              },
            ]}
          />
        )}
      </QueryView>
      <NewQuestionDialog open={creating} onOpenChange={setCreating} />
    </div>
  );
}
