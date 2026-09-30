import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { assessmentsApi, type Slot, type StudentAttempt, type TestItem, type TestQuestion } from "@/api/assessments";
import { errorMessage } from "@/api/client";
import { KeyValue, Note, PageHead, QueryView, Section, StatusBadge, StatusNote } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { clock, formatIst } from "@/lib/format";
import { useApiMutation } from "@/lib/mutation";

type Answers = Record<string, unknown>;

// ---------------------------------------------------------------- one question

function QuestionField({
  question,
  value,
  onChange,
  disabled,
}: {
  question: TestQuestion;
  value: unknown;
  onChange: (value: unknown) => void;
  disabled: boolean;
}) {
  const id = `q-${question.question_id}`;
  switch (question.question_type) {
    case "Single choice":
      return (
        <div>
          {question.options.map((o) => (
            <label key={o.key} className="tap flex items-center gap-2">
              <input type="radio" name={id} checked={value === o.key} disabled={disabled} onChange={() => onChange(o.key)} /> {o.text}
            </label>
          ))}
        </div>
      );
    case "Multiple choice": {
      const chosen = Array.isArray(value) ? (value as string[]) : [];
      return (
        <div>
          {question.options.map((o) => (
            <label key={o.key} className="tap flex items-center gap-2">
              <input
                type="checkbox"
                checked={chosen.includes(o.key)}
                disabled={disabled}
                onChange={(e) => onChange(e.target.checked ? [...chosen, o.key] : chosen.filter((k) => k !== o.key))}
              />{" "}
              {o.text}
            </label>
          ))}
        </div>
      );
    }
    case "True / False":
      return (
        <div>
          {[true, false].map((v) => (
            <label key={String(v)} className="tap flex items-center gap-2">
              <input type="radio" name={id} checked={value === v} disabled={disabled} onChange={() => onChange(v)} /> {v ? "True" : "False"}
            </label>
          ))}
        </div>
      );
    case "Numeric":
      return (
        <Input
          id={id}
          aria-label="Your answer"
          inputMode="decimal"
          disabled={disabled}
          value={value === undefined || value === null ? "" : String(value)}
          onChange={(e) => onChange(e.target.value === "" || Number.isNaN(Number(e.target.value)) ? undefined : Number(e.target.value))}
        />
      );
    case "Descriptive":
      return (
        <Textarea id={id} aria-label="Your answer" rows={4} disabled={disabled} value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value)} />
      );
    case "Coding":
      return (
        <>
          <Textarea
            id={id}
            aria-label="Your code"
            rows={7}
            spellCheck={false}
            disabled={disabled}
            className="bg-navy font-mono text-sm text-navy-foreground"
            value={(value as string) ?? ""}
            onChange={(e) => onChange(e.target.value)}
          />
          <p className="mt-1 text-xs text-muted-foreground">Code execution: Integration Unavailable. Your trainer reads and marks your code.</p>
        </>
      );
    default:
      return <Input id={id} aria-label="Your answer" disabled={disabled} value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value)} />;
  }
}

// ---------------------------------------------------------------- the running attempt

function AttemptRunner({ initial, onDone }: { initial: StudentAttempt; onDone: () => void }) {
  const attemptId = initial.attempt.attempt_id;
  const [answers, setAnswers] = useState<Answers>(initial.answers);
  const [saved, setSaved] = useState<"Saved" | "Saving" | "Failed" | null>("Saved");
  const dirty = useRef(false);
  // The server's clock decides: remaining time is measured from the deadline, corrected for this device's clock skew.
  const skew = useMemo(() => new Date(initial.server_time).getTime() - Date.now(), [initial.server_time]);
  const deadline = initial.attempt.deadline_at ? new Date(initial.attempt.deadline_at).getTime() : null;
  const [left, setLeft] = useState<number | null>(deadline ? Math.max(Math.floor((deadline - Date.now() - skew) / 1000), 0) : null);
  const finished = useRef(false);

  const finish = useCallback(async () => {
    if (finished.current) return;
    finished.current = true;
    onDone();
  }, [onDone]);

  const save = useCallback(async () => {
    if (!dirty.current || finished.current) return;
    dirty.current = false;
    setSaved("Saving");
    try {
      const result = await assessmentsApi.saveAnswers(attemptId, answers);
      if (!result.accepted) await finish();
      else setSaved("Saved");
    } catch {
      dirty.current = true;
      setSaved("Failed");
    }
  }, [answers, attemptId, finish]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (deadline) {
        const remaining = Math.max(Math.floor((deadline - Date.now() - skew) / 1000), 0);
        setLeft(remaining);
        if (remaining === 0) void assessmentsApi.attempt(attemptId).then(finish, finish);
      }
    }, 1000);
    return () => window.clearInterval(timer);
  }, [deadline, skew, attemptId, finish]);

  useEffect(() => {
    const autosave = window.setInterval(() => void save(), 10_000);
    return () => window.clearInterval(autosave);
  }, [save]);

  const submit = useApiMutation(() => assessmentsApi.submitAttempt(attemptId, answers), { success: "Test submitted", onSuccess: () => void finish() });

  return (
    <div>
      <div className="sticky top-[90px] z-30 mb-4 flex flex-wrap items-center gap-3 rounded-xl border bg-card p-3 shadow-sm">
        <span className="font-mono text-lg font-semibold" aria-label="Time remaining">
          {left === null ? "No time limit" : clock(left)}
        </span>
        <span className="text-xs text-muted-foreground">Server-authoritative timer — closing the tab does not pause time.</span>
        <div className="ml-auto">
          {saved === "Saved" && <StatusNote state="Saved" />}
          {saved === "Saving" && <StatusNote state="Saving" />}
          {saved === "Failed" && (
            <StatusNote state="Failed">Connection interrupted. Your last saved answers are kept; we will retry. The server timer continues.</StatusNote>
          )}
        </div>
      </div>
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          submit.mutate(undefined);
        }}
      >
        {initial.questions.map((q) => (
          <fieldset key={q.question_id} className="rounded-xl border bg-card p-4">
            <legend className="px-1 text-sm font-semibold">
              Q{q.position} · <span className="text-muted-foreground">{q.question_type}</span> · {q.marks} marks
            </legend>
            <p className="mb-2 whitespace-pre-wrap text-sm">{q.stem}</p>
            <QuestionField
              question={q}
              value={answers[String(q.question_id)]}
              disabled={false}
              onChange={(value) => {
                dirty.current = true;
                setSaved(null);
                setAnswers((prev) => ({ ...prev, [String(q.question_id)]: value }));
              }}
            />
          </fieldset>
        ))}
        <Button type="submit" disabled={submit.isPending}>
          {submit.isPending ? "Submitting…" : "Submit test"}
        </Button>
      </form>
    </div>
  );
}

// ---------------------------------------------------------------- interview booking

function InterviewSlots({ test }: { test: TestItem }) {
  const slots = useQuery({ queryKey: ["tests", "slots", test.test_id], queryFn: () => assessmentsApi.slots(test.test_id) });
  const refresh = [["tests"]];
  const book = useApiMutation((slot: Slot) => assessmentsApi.bookSlot(slot.slot_id), {
    success: "Slot booked — waiting for your trainer to confirm",
    invalidate: refresh,
  });
  const cancel = useApiMutation((slot: Slot) => assessmentsApi.cancelSlot(slot.slot_id), { success: "Booking cancelled", invalidate: refresh });
  const mine = test.my?.slot;
  return (
    <Section title="Mock interview slots">
      {mine && (
        <div className="mb-3 rounded-lg border p-3 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <strong>Your slot: {formatIst(mine.starts_at)}</strong>
            <StatusBadge>{mine.status}</StatusBadge>
          </div>
          {mine.status === "Completed" && (
            <p className="mt-2">
              Rating {mine.rating}/5. Strengths: {mine.strengths}. To improve: {mine.improvements}. Next practice: {mine.next_action}.
            </p>
          )}
          {(mine.status === "Slot Confirmation Pending" || mine.status === "Confirmed") && (
            <Button className="mt-2" variant="outline" size="sm" onClick={() => cancel.mutate(mine)}>
              Cancel booking
            </Button>
          )}
        </div>
      )}
      <QueryView query={slots} isEmpty={(s) => s.length === 0} empty="Your trainer has not offered slots yet.">
        {(items) => (
          <ul className="space-y-2">
            {items
              .filter((s) => s.status === "Open")
              .map((s) => (
                <li key={s.slot_id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border p-3 text-sm">
                  <span>
                    {formatIst(s.starts_at)} with {s.trainer.full_name}
                  </span>
                  <Button size="sm" disabled={!!mine && mine.status !== "Cancelled"} onClick={() => book.mutate(s)}>
                    Book this slot
                  </Button>
                </li>
              ))}
          </ul>
        )}
      </QueryView>
      <div className="mt-3">
        <Note>Practice only: interview feedback carries no marks and is not a promise of placement.</Note>
      </div>
    </Section>
  );
}

// ---------------------------------------------------------------- the screen

export function TestDetail() {
  const { id } = useParams({ from: "/tests/$id" });
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["tests", "detail", id], queryFn: () => assessmentsApi.test(Number(id)) });
  const [running, setRunning] = useState<StudentAttempt | null>(null);
  const [receipt, setReceipt] = useState<StudentAttempt | null>(null);

  const refresh = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: ["tests"] });
    await queryClient.invalidateQueries({ queryKey: ["results"] });
  }, [queryClient]);

  const start = useApiMutation(() => assessmentsApi.startAttempt(Number(id)), { onSuccess: (attempt) => setRunning(attempt) });

  const finishRunning = useCallback(async () => {
    if (!running) return;
    try {
      setReceipt(await assessmentsApi.attempt(running.attempt.attempt_id));
    } finally {
      setRunning(null);
      await refresh();
    }
  }, [running, refresh]);

  return (
    <div className="mx-auto max-w-4xl">
      <QueryView query={query}>
        {(test) => (
          <>
            <nav className="mb-2 text-sm">
              <Link to="/tests" className="text-primary underline">
                Tests
              </Link>{" "}
              / {test.title}
            </nav>
            <PageHead title={test.title} actions={<StatusBadge tone="info">{test.kind}</StatusBadge>} />
            {running ? (
              <AttemptRunner initial={running} onDone={() => void finishRunning()} />
            ) : (
              <div className="space-y-4">
                <Section>
                  <KeyValue
                    items={[
                      ["Status", <StatusBadge key="s">{test.my?.my_status ?? test.status}</StatusBadge>],
                      ["Duration", test.duration_minutes ? `${test.duration_minutes} minutes` : "Untimed"],
                      ["Opens", formatIst(test.opens_at)],
                      ["Closes", formatIst(test.closes_at)],
                      ["Questions", String(test.question_count)],
                      ["Total marks", test.total_marks ?? "—"],
                      ["Attempts remaining", test.my?.attempts_remaining === null ? "Repeat within the window" : String(test.my?.attempts_remaining ?? "—")],
                      ["AI use", test.ai_use_rule],
                    ]}
                  />
                  {test.instructions && <p className="mt-3 text-sm">{test.instructions}</p>}
                  {test.kind !== "Mock interview" && (
                    <div className="mt-4 flex flex-wrap items-center gap-3">
                      <Button disabled={!test.my?.can_start || start.isPending} onClick={() => start.mutate(undefined)}>
                        {test.my?.in_progress_attempt_id ? "Resume test" : "Start test"}
                      </Button>
                      {!test.my?.can_start && !test.my?.in_progress_attempt_id && (
                        <span className="text-sm text-muted-foreground">
                          {test.status === "Available" ? "You have used every attempt." : `This test is ${test.status}.`}
                        </span>
                      )}
                      {start.isError && <StatusNote state="Failed">{errorMessage(start.error)}</StatusNote>}
                    </div>
                  )}
                </Section>
                {receipt && (
                  <Section title="Submission Receipt">
                    <p className="text-sm">
                      Receipt <strong>{receipt.attempt.receipt_code}</strong> · {formatIst(receipt.attempt.submitted_at)}
                      {receipt.attempt.submit_reason === "Timeout" && " (time ran out: your saved answers were submitted)"}.
                    </p>
                    {receipt.attempt.score !== undefined && receipt.attempt.score !== null && (
                      <p className="mt-1 text-sm">
                        Score: {receipt.attempt.score} / {receipt.attempt.total_marks}
                      </p>
                    )}
                    {receipt.test.is_formal && (
                      <p className="mt-1 text-sm text-muted-foreground">Your score is withheld until your Academic Coordinator publishes the result.</p>
                    )}
                  </Section>
                )}
                {!receipt && test.my?.latest_attempt?.receipt_code && (
                  <Section title="Submission Receipt">
                    <p className="text-sm">
                      Receipt <strong>{test.my.latest_attempt.receipt_code}</strong> · {formatIst(test.my.latest_attempt.submitted_at)}
                      {test.my.latest_attempt.score ? ` · Score ${test.my.latest_attempt.score} / ${test.total_marks}` : ""}
                    </p>
                  </Section>
                )}
                {test.kind === "Mock interview" && <InterviewSlots test={test} />}
                <Note>Assessment completion does not equal attendance, course completion or certificate issue.</Note>
              </div>
            )}
          </>
        )}
      </QueryView>
    </div>
  );
}
