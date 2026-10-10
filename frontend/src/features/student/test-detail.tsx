import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { Flag } from "lucide-react";
import { assessmentsApi, type Slot, type StudentAttempt, type TestItem, type TestQuestion } from "@/api/assessments";
import { errorMessage } from "@/api/client";
import { Breadcrumbs } from "@/components/lms/breadcrumbs";
import { ConfirmDialog } from "@/components/lms/confirm-dialog";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { KeyValue, Note, PageHead, QueryView, Section, StatusBadge, StatusNote, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { fmtDateTime } from "@/features/shared/format";
import { clock } from "@/lib/format";
import { useApiMutation } from "@/lib/mutation";
import { useT, type TranslationKey } from "@/lib/i18n";
import { cn } from "@/lib/utils";

type Answers = Record<string, unknown>;
type T = ReturnType<typeof useT>;

const KIND_KEY: Record<string, TranslationKey> = {
  "Practice quiz": "kindPracticeQuiz",
  "Module test": "kindModuleTest",
  "Final test": "kindFinalTest",
  "Coding exercise": "kindCodingExercise",
  "Mock test": "kindMockTest",
  "Mock interview": "kindMockInterview",
};

const QUESTION_TYPE_KEY: Record<string, TranslationKey> = {
  "Single choice": "qtSingle",
  "Multiple choice": "qtMultiple",
  "True / False": "qtTrueFalse",
  Numeric: "qtNumeric",
  Descriptive: "qtDescriptive",
  Coding: "qtCoding",
  "Short answer": "qtShort",
};

const kindLabel = (t: T, kind: string) => (KIND_KEY[kind] ? t(KIND_KEY[kind]) : kind);

/** Whether a question has an answer: a chosen option, a number (zero counts) or some text. */
function isAnswered(value: unknown): boolean {
  if (value === undefined || value === null) return false;
  if (typeof value === "string") return value.trim() !== "";
  if (Array.isArray(value)) return value.length > 0;
  return true;
}

/** The student's state for a test: their booking or attempt first, otherwise whether the test is open. */
export function MyTestStatus({ test }: { test: TestItem }) {
  const t = useT();
  const mine = test.my?.my_status;
  if (mine) {
    if (mine.startsWith("Submitted")) return <StatusBadge domain="work" code="Submitted" />;
    if (mine === "In progress") return <StatusBadge domain="test" code="In progress" />;
    return <StatusBadge domain="slot" code={mine} />;
  }
  if (test.status === "Scheduled") return <StatusBadge domain="test" code="Scheduled" label={t("opensAt", { when: fmtDateTime(test.opens_at) })} />;
  return <StatusBadge domain="test" code={test.status === "Available" ? "Released" : test.status} />;
}

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
  const t = useT();
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
              <input type="radio" name={id} checked={value === v} disabled={disabled} onChange={() => onChange(v)} /> {v ? t("trueLabel") : t("falseLabel")}
            </label>
          ))}
        </div>
      );
    case "Numeric":
      return (
        <Input
          id={id}
          aria-label={t("yourAnswer")}
          inputMode="decimal"
          disabled={disabled}
          value={value === undefined || value === null ? "" : String(value)}
          onChange={(e) => onChange(e.target.value === "" || Number.isNaN(Number(e.target.value)) ? undefined : Number(e.target.value))}
        />
      );
    case "Descriptive":
      return (
        <Textarea id={id} aria-label={t("yourAnswer")} rows={4} disabled={disabled} value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value)} />
      );
    case "Coding":
      return (
        <>
          <Textarea
            id={id}
            aria-label={t("yourCode")}
            rows={7}
            spellCheck={false}
            disabled={disabled}
            className="bg-navy font-mono text-sm text-navy-foreground"
            value={(value as string) ?? ""}
            onChange={(e) => onChange(e.target.value)}
          />
          <p className="mt-1 text-xs text-muted-foreground">{t("codeNotRun")}</p>
        </>
      );
    default:
      return <Input id={id} aria-label={t("yourAnswer")} disabled={disabled} value={(value as string) ?? ""} onChange={(e) => onChange(e.target.value)} />;
  }
}

// ---------------------------------------------------------------- question navigator

/** Numbered buttons for every question: filled when answered, flagged ones carry a flag. Click to jump to a question. */
function QuestionNavigator({ questions, answers, flagged }: { questions: TestQuestion[]; answers: Answers; flagged: Set<number> }) {
  const t = useT();
  const answered = questions.filter((q) => isAnswered(answers[String(q.question_id)])).length;
  return (
    <nav aria-label={t("navigatorTitle")} className="rounded-xl border bg-card p-3 shadow-sm lg:order-2 lg:sticky lg:top-[170px] lg:self-start">
      <p className="text-sm font-semibold">{t("navigatorTitle")}</p>
      <p className="text-xs text-muted-foreground" aria-live="polite">
        {t("navSummary", { answered, total: questions.length })}
        {flagged.size > 0 && ` · ${t("navFlaggedCount", { n: flagged.size })}`}
      </p>
      <ol className="mt-2 flex flex-wrap gap-1.5">
        {questions.map((q) => {
          const done = isAnswered(answers[String(q.question_id)]);
          const marked = flagged.has(q.question_id);
          return (
            <li key={q.question_id}>
              <button
                type="button"
                aria-label={`${t("goToQuestion", { n: q.position })}: ${done ? t("navAnswered") : t("navNotAnswered")}${marked ? `, ${t("navFlagged")}` : ""}`}
                className={cn(
                  "tap relative grid size-9 place-items-center rounded-md border text-sm font-medium",
                  done ? "border-primary bg-primary text-primary-foreground" : "bg-background hover:bg-accent",
                  marked && "ring-2 ring-amber-500",
                )}
                onClick={() => document.getElementById(`question-${q.question_id}`)?.scrollIntoView({ behavior: "smooth", block: "center" })}
              >
                {q.position}
                {marked && <Flag className="absolute -right-1 -top-1 size-3.5 fill-amber-500 text-amber-600" aria-hidden />}
              </button>
            </li>
          );
        })}
      </ol>
      <ul className="mt-3 space-y-1 text-xs text-muted-foreground">
        <li className="flex items-center gap-2">
          <span className="size-3 rounded-sm border border-primary bg-primary" aria-hidden /> {t("navAnswered")}
        </li>
        <li className="flex items-center gap-2">
          <span className="size-3 rounded-sm border bg-background" aria-hidden /> {t("navNotAnswered")}
        </li>
        <li className="flex items-center gap-2">
          <Flag className="size-3 fill-amber-500 text-amber-600" aria-hidden /> {t("navFlagged")}
        </li>
      </ul>
    </nav>
  );
}

// ---------------------------------------------------------------- the running attempt

function AttemptRunner({ initial, onDone }: { initial: StudentAttempt; onDone: () => void }) {
  const t = useT();
  const attemptId = initial.attempt.attempt_id;
  const [answers, setAnswers] = useState<Answers>(initial.answers);
  const [flagged, setFlagged] = useState<Set<number>>(() => new Set());
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

  const submit = useApiMutation(() => assessmentsApi.submitAttempt(attemptId, answers), {
    success: t("testSubmittedToast"),
    next: t("testSubmittedNext"),
    view: { to: "/tasks", label: t("backToTasks") },
    onSuccess: () => void finish(),
  });

  const total = initial.questions.length;
  const unanswered = initial.questions.filter((q) => !isAnswered(answers[String(q.question_id)])).length;
  const consequence = (
    <>
      {unanswered > 0 ? t("submitUnanswered", { n: unanswered, total }) : t("submitAllAnswered", { total })}
      {flagged.size > 0 && <> {t("submitFlaggedExtra", { n: flagged.size })}</>}
    </>
  );
  const toggleFlag = (id: number) =>
    setFlagged((prev) => {
      const next = new Set(prev);
      if (!next.delete(id)) next.add(id);
      return next;
    });

  return (
    <div>
      <div className="sticky top-[90px] z-30 mb-4 flex flex-wrap items-center gap-3 rounded-xl border bg-card p-3 shadow-sm">
        <span className="font-mono text-lg font-semibold" aria-label={t("timeRemaining")}>
          {left === null ? t("untimed") : clock(left)}
        </span>
        <span className="text-xs text-muted-foreground">{t("timerNote")}</span>
        <div className="ml-auto">
          {saved === "Saved" && <StatusNote tone="success">{t("savedState")}</StatusNote>}
          {saved === "Saving" && <StatusNote tone="info">{t("savingState")}</StatusNote>}
          {saved === "Failed" && <StatusNote tone="danger">{t("saveFailed")}</StatusNote>}
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_15rem]">
        <QuestionNavigator questions={initial.questions} answers={answers} flagged={flagged} />
        <form className="space-y-4 lg:order-1" onSubmit={(e) => e.preventDefault()}>
          {initial.questions.map((q) => {
            const marked = flagged.has(q.question_id);
            const typeKey = QUESTION_TYPE_KEY[q.question_type];
            return (
              <fieldset key={q.question_id} id={`question-${q.question_id}`} className={cn("scroll-mt-40 rounded-xl border bg-card p-4", marked && "border-amber-500")}>
                <legend className="px-1 text-sm font-semibold">
                  {t("questionN", { n: q.position })} · <span className="text-muted-foreground">{typeKey ? t(typeKey) : q.question_type}</span> ·{" "}
                  {t("questionMarks", { marks: q.marks })}
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
                <Button type="button" variant="ghost" size="sm" className="mt-2" aria-pressed={marked} onClick={() => toggleFlag(q.question_id)}>
                  <Flag className={cn("size-4", marked && "fill-amber-500 text-amber-600")} aria-hidden />
                  {marked ? t("unflagQuestion") : t("flagQuestion")}
                </Button>
              </fieldset>
            );
          })}
          <ConfirmDialog title={t("submitTestTitle")} consequence={consequence} confirmLabel={t("submitNow")} cancelLabel={t("cancel")} onConfirm={() => submit.mutate(undefined)}>
            <Button type="button" disabled={submit.isPending}>
              {submit.isPending ? t("submitting") : t("submitTest")}
            </Button>
          </ConfirmDialog>
        </form>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- interview booking

function InterviewSlots({ test }: { test: TestItem }) {
  const t = useT();
  const slots = useQuery({ queryKey: ["tests", "slots", test.test_id], queryFn: () => assessmentsApi.slots(test.test_id) });
  const refresh = [["tests"], ["work"], ["nav"]];
  const book = useApiMutation((slot: Slot) => assessmentsApi.bookSlot(slot.slot_id), {
    success: t("slotBooked"),
    next: t("slotBookedNext"),
    view: { to: "/tasks", label: t("backToTasks") },
    invalidate: refresh,
  });
  const cancel = useApiMutation((slot: Slot) => assessmentsApi.cancelSlot(slot.slot_id), { success: t("bookingCancelled"), invalidate: refresh });
  const mine = test.my?.slot;
  return (
    <Section title={t("mockSlots")}>
      {mine && (
        <div className="mb-3 rounded-lg border p-3 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <strong>{t("yourSlot", { when: fmtDateTime(mine.starts_at) })}</strong>
            <StatusBadge domain="slot" code={mine.status} />
          </div>
          {mine.status === "Completed" && (
            <p className="mt-2">
              {t("interviewFeedback", { rating: mine.rating ?? "—", strengths: mine.strengths ?? "—", improvements: mine.improvements ?? "—", next: mine.next_action ?? "—" })}
            </p>
          )}
          {(mine.status === "Slot Confirmation Pending" || mine.status === "Confirmed") && (
            <ConfirmDialog
              title={t("cancelBooking")}
              consequence={t("yourSlot", { when: fmtDateTime(mine.starts_at) })}
              confirmLabel={t("cancelBooking")}
              cancelLabel={t("cancel")}
              destructive
              onConfirm={() => cancel.mutate(mine)}
            >
              <Button className="mt-2" variant="outline" size="sm">
                {t("cancelBooking")}
              </Button>
            </ConfirmDialog>
          )}
        </div>
      )}
      <QueryView query={slots} isEmpty={(s) => s.length === 0} empty={t("noSlots")}>
        {(items) => (
          <ul className="space-y-2">
            {items
              .filter((s) => s.status === "Open")
              .map((s) => (
                <li key={s.slot_id} className="flex flex-wrap items-center justify-between gap-2 rounded-lg border p-3 text-sm">
                  <span>{t("slotWith", { when: fmtDateTime(s.starts_at), name: s.trainer.full_name })}</span>
                  <Button size="sm" disabled={!!mine && mine.status !== "Cancelled"} onClick={() => book.mutate(s)}>
                    {t("bookThisSlot")}
                  </Button>
                </li>
              ))}
          </ul>
        )}
      </QueryView>
      <div className="mt-3">
        <Note>{t("practiceOnly")}</Note>
      </div>
    </Section>
  );
}

// ---------------------------------------------------------------- after submitting

/** The receipt, with where the result will appear and the way back to the task list. */
function Receipt({ code, submittedAt, timedOut, score, total, formal }: { code: string; submittedAt: string | null; timedOut: boolean; score: string | null; total: string | null; formal: boolean }) {
  const t = useT();
  return (
    <Section title={t("receiptTitle")}>
      <p className="text-sm">
        {t("receiptLine", { code, when: fmtDateTime(submittedAt) })}
        {timedOut && ` ${t("timedOutNote")}`}
      </p>
      {score !== null && (
        <p className="mt-1 text-sm font-medium">{t("scoreLine", { marks: score, max: total ?? "—" })}</p>
      )}
      <p className="mt-1 text-sm text-muted-foreground">{formal ? t("scoreWithheld") : t("scoreShownAbove")}</p>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button asChild>
          <Link to="/tasks">{t("backToTasks")}</Link>
        </Button>
        {formal && (
          <Button asChild variant="outline">
            <Link to="/results">{t("seeResults")}</Link>
          </Button>
        )}
      </div>
    </Section>
  );
}

// ---------------------------------------------------------------- the screen

export function TestDetail() {
  const t = useT();
  const { id } = useParams({ from: "/tests/$id" });
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["tests", "detail", id], queryFn: () => assessmentsApi.test(Number(id)) });
  const [running, setRunning] = useState<StudentAttempt | null>(null);
  const [receipt, setReceipt] = useState<StudentAttempt | null>(null);

  const refresh = useCallback(async () => {
    await Promise.all(["tests", "results", "work", "nav"].map((key) => queryClient.invalidateQueries({ queryKey: [key] })));
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
    <div className="mx-auto max-w-5xl">
      <QueryView query={query} skeleton="detail">
        {(test) => {
          const my = test.my;
          const resuming = !!my?.in_progress_attempt_id;
          const attemptsText = my?.attempts_remaining === null || my?.attempts_remaining === undefined ? t("attemptsUnlimited") : String(my.attempts_remaining);
          const blocked = !my?.can_start && !resuming;
          const blockedText =
            test.status === "Available"
              ? t("testUsedAll")
              : test.status === "Scheduled"
                ? t("testNotOpenYet", { when: fmtDateTime(test.opens_at) })
                : test.status === "Closed"
                  ? t("testClosed")
                  : t("testNotReleased");
          const startButton = (
            <Button disabled={blocked || start.isPending}>{resuming ? t("actionResumeTest") : t("actionStartTest")}</Button>
          );
          return (
            <>
              <Breadcrumbs items={[{ label: t("tasksAndTests"), to: "/tasks" }, { label: test.title }]} />
              <PageHead title={test.title} actions={<Tag tone="info">{kindLabel(t, test.kind)}</Tag>} />
              {running ? (
                <AttemptRunner initial={running} onDone={() => void finishRunning()} />
              ) : (
                <div className="space-y-4">
                  <Section>
                    <KeyValue
                      items={[
                        [t("statusLabel"), <MyTestStatus key="s" test={test} />],
                        [t("durationLabel"), test.duration_minutes ? t("minutesN", { n: test.duration_minutes }) : t("untimed")],
                        [t("opensLabel"), fmtDateTime(test.opens_at)],
                        [t("closesLabel"), fmtDateTime(test.closes_at)],
                        [t("questionsLabel"), String(test.question_count)],
                        [t("totalMarksLabel"), test.total_marks ?? "—"],
                        [t("attemptsLeftLabel"), my?.attempts_remaining === null ? t("repeatInWindow") : String(my?.attempts_remaining ?? "—")],
                        [t("aiUseLabel"), test.ai_use_rule],
                      ]}
                    />
                    {test.instructions && <p className="mt-3 text-sm">{test.instructions}</p>}
                    {test.kind !== "Mock interview" && (
                      <div className="mt-4 flex flex-wrap items-center gap-3">
                        {resuming || blocked ? (
                          <Button disabled={blocked || start.isPending} onClick={() => start.mutate(undefined)}>
                            {resuming ? t("actionResumeTest") : t("actionStartTest")}
                          </Button>
                        ) : (
                          <ConfirmDialog
                            title={t("startTestTitle")}
                            consequence={
                              test.duration_minutes
                                ? t("startTimed", { n: test.duration_minutes, attempts: attemptsText })
                                : t("startUntimed", { attempts: attemptsText })
                            }
                            confirmLabel={t("startNow")}
                            cancelLabel={t("cancel")}
                            onConfirm={() => start.mutate(undefined)}
                          >
                            {startButton}
                          </ConfirmDialog>
                        )}
                        {blocked && <span className="text-sm text-muted-foreground">{blockedText}</span>}
                        {start.isError && (
                          <StatusNote tone="danger" title={t("couldNotStart")}>
                            {errorMessage(start.error)}
                          </StatusNote>
                        )}
                      </div>
                    )}
                  </Section>
                  {receipt && (
                    <Receipt
                      code={receipt.attempt.receipt_code ?? "—"}
                      submittedAt={receipt.attempt.submitted_at}
                      timedOut={receipt.attempt.submit_reason === "Timeout"}
                      score={receipt.attempt.score !== undefined && receipt.attempt.score !== null ? String(receipt.attempt.score) : null}
                      total={receipt.attempt.total_marks}
                      formal={receipt.test.is_formal}
                    />
                  )}
                  {!receipt && my?.latest_attempt?.receipt_code && (
                    <Receipt
                      code={my.latest_attempt.receipt_code}
                      submittedAt={my.latest_attempt.submitted_at}
                      timedOut={false}
                      score={my.latest_attempt.score ? String(my.latest_attempt.score) : null}
                      total={test.total_marks ?? null}
                      formal={test.is_formal}
                    />
                  )}
                  {test.kind === "Mock interview" && <InterviewSlots test={test} />}
                  <HowThisWorks title={t("howMarksWork")}>
                    <p>{t("howMarksText1")}</p>
                    <p>{t("howMarksText2")}</p>
                  </HowThisWorks>
                </div>
              )}
            </>
          );
        }}
      </QueryView>
    </div>
  );
}
