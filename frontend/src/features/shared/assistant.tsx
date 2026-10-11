/**
 * Ask Nipuna as a chat: the conversation reads oldest first, the box is pinned under it, quick actions fill the box (they never
 * override what was typed), sources are links, and a question Ask Nipuna cannot answer can be sent to a person. One component for
 * the student assistant and the trainer's (`variant`): they differ in example prompts, where a source opens and the support offer.
 */
import { useEffect, useRef, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { LifeBuoy, Send, Sparkles, ThumbsDown, ThumbsUp, X } from "lucide-react";
import { askApi, type AiAnswer, type AssistantStatus } from "@/api/ask-nipuna";
import { HowThisWorks } from "@/components/lms/how-this-works";
import { PageHead, QueryView, StatusNote, Tag } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useApiMutation } from "@/lib/mutation";
import { useT, type TranslationKey } from "@/lib/i18n";
import { cn } from "@/lib/utils";

export type AssistantVariant = "student" | "trainer";

/** Each quick action: its label, and the start of the question it puts in the box. The API receives the English action name. */
const ACTIONS: Record<string, { label: TranslationKey; start: TranslationKey }> = {
  "Ask about my course": { label: "an_act_course", start: "an_start_course" },
  "Explain this topic": { label: "an_act_explain", start: "an_start_explain" },
  Summarize: { label: "an_act_summarize", start: "an_start_summarize" },
  "Generate practice questions": { label: "an_act_practice", start: "an_start_practice" },
  "Career guidance": { label: "an_act_career", start: "an_start_career" },
  "Explain my progress": { label: "an_act_progress", start: "an_start_progress" },
  "Draft practice questions": { label: "an_act_draft", start: "an_start_draft" },
  "Summarize batch progress": { label: "an_act_batch", start: "an_start_batch" },
  "Explain topic for class": { label: "an_act_class_topic", start: "an_start_class_topic" },
  "Suggest feedback wording": { label: "an_act_feedback", start: "an_start_feedback" },
};

const EXAMPLES: Record<AssistantVariant, TranslationKey[]> = {
  student: ["an_ex_s1", "an_ex_s2", "an_ex_s3", "an_ex_s4"],
  trainer: ["an_ex_t1", "an_ex_t2", "an_ex_t3", "an_ex_t4"],
};

/** Quota is only worth a line once most of it is used. */
const NEAR_LIMIT = 0.8;

type Pending = { question: string; action: string | null };

export function Assistant({ variant }: { variant: AssistantVariant }) {
  const t = useT();
  const student = variant === "student";
  const [question, setQuestion] = useState("");
  const [action, setAction] = useState<string | null>(null);
  const [pending, setPending] = useState<Pending | null>(null);
  const status = useQuery({ queryKey: ["ask", "status"], queryFn: askApi.status });
  const history = useQuery({ queryKey: ["ask", "history"], queryFn: () => askApi.history() });
  const box = useRef<HTMLTextAreaElement>(null);
  const lastStart = useRef("");

  const ask = useApiMutation((vars: Pending) => askApi.ask(vars.question, vars.action ?? undefined), {
    invalidate: [["ask"]],
    onSuccess: () => setPending(null),
    onError: (_error) => {
      // Keep what the person wrote: it goes back in the box so nothing is lost
      setQuestion((current) => current || pending?.question || "");
      setAction((current) => current ?? pending?.action ?? null);
      setPending(null);
    },
  });
  const feedback = useApiMutation((vars: { id: number; rating: "Helpful" | "Not helpful" }) => askApi.feedback(vars.id, vars.rating), {
    invalidate: [["ask", "history"]],
    success: t("an_thanks"),
  });

  function send() {
    const text = question.trim();
    if (!text || ask.isPending) return;
    const next = { question: text, action };
    setPending(next);
    setQuestion("");
    setAction(null);
    lastStart.current = "";
    ask.mutate(next);
  }

  /** A quick action fills the box and says so. Text the person already typed is kept: the action then applies to it. */
  function pick(name: string) {
    if (action === name) {
      setAction(null);
      return;
    }
    setAction(name);
    const spec = ACTIONS[name];
    if (spec && (question.trim() === "" || question === lastStart.current)) {
      const start = t(spec.start);
      lastStart.current = start;
      setQuestion(start);
    }
    box.current?.focus();
  }

  function useExample(key: TranslationKey) {
    setQuestion(t(key));
    lastStart.current = "";
    box.current?.focus();
  }

  return (
    <div className="mx-auto max-w-4xl">
      <PageHead title={student ? t("askNipuna") : t("an_title_trainer")} description={student ? t("an_desc_student") : t("an_desc_trainer")} />
      <QueryView query={status} skeleton="detail">
        {(s) => (
          <ChatPanel
            variant={variant}
            status={s}
            thread={history.data?.data ?? []}
            historyLoading={history.isPending}
            pending={ask.isPending ? pending : null}
            question={question}
            onQuestion={setQuestion}
            action={action}
            onPick={pick}
            onClearAction={() => setAction(null)}
            onSend={send}
            onExample={useExample}
            onRate={(id, rating) => feedback.mutate({ id, rating })}
            box={box}
          />
        )}
      </QueryView>
      <div className="mt-4">
        <HowThisWorks title={t("an_how_title")}>
          <p>{t("an_how_advice")}</p>
          <p className="mt-2">{t("an_how_scope")}</p>
        </HowThisWorks>
      </div>
    </div>
  );
}

function ChatPanel({
  variant,
  status,
  thread,
  historyLoading,
  pending,
  question,
  onQuestion,
  action,
  onPick,
  onClearAction,
  onSend,
  onExample,
  onRate,
  box,
}: {
  variant: AssistantVariant;
  status: AssistantStatus;
  thread: AiAnswer[];
  historyLoading: boolean;
  pending: Pending | null;
  question: string;
  onQuestion: (text: string) => void;
  action: string | null;
  onPick: (name: string) => void;
  onClearAction: () => void;
  onSend: () => void;
  onExample: (key: TranslationKey) => void;
  onRate: (id: number, rating: "Helpful" | "Not helpful") => void;
  box: React.RefObject<HTMLTextAreaElement | null>;
}) {
  const t = useT();
  const blocked = status.status === "Quota Limited" || status.status === "Disabled";
  const scroller = useRef<HTMLDivElement>(null);
  const nearLimit = !blocked && status.usage.limit > 0 && status.usage.used >= Math.ceil(status.usage.limit * NEAR_LIMIT);
  const empty = thread.length === 0 && !pending;

  useEffect(() => {
    const el = scroller.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [thread.length, pending]);

  return (
    <section
      aria-label={t("an_conversation")}
      className="flex h-[calc(100dvh-14rem)] min-h-[26rem] flex-col rounded-xl border bg-card shadow-sm md:h-[calc(100dvh-11rem)]"
    >
      <div ref={scroller} className="flex-1 space-y-4 overflow-y-auto p-4" role="log" aria-live="polite" data-testid="ask-thread">
        {historyLoading && <p className="text-sm text-muted-foreground">{t("an_loading")}</p>}
        {empty && !historyLoading && (
          <div className="mx-auto max-w-md space-y-3 py-6 text-center">
            <Sparkles className="mx-auto size-7 text-primary" aria-hidden />
            <p className="font-medium">{t(variant === "student" ? "an_welcome_student" : "an_welcome_trainer")}</p>
            <p className="text-sm text-muted-foreground">{t("an_try")}</p>
            <ul className="flex flex-wrap justify-center gap-2">
              {EXAMPLES[variant].map((key) => (
                <li key={key}>
                  <button
                    type="button"
                    onClick={() => onExample(key)}
                    disabled={blocked}
                    className="tap rounded-full border bg-background px-3 py-1.5 text-sm hover:bg-accent disabled:opacity-50"
                  >
                    {t(key)}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
        {thread.map((item) => (
          <Exchange key={item.ai_query_id} item={item} variant={variant} onRate={onRate} />
        ))}
        {pending && (
          <>
            <Bubble mine>
              <p className="whitespace-pre-wrap break-words">{pending.question}</p>
            </Bubble>
            <Bubble>
              <p className="text-muted-foreground" role="status">
                {t("an_thinking")}
              </p>
            </Bubble>
          </>
        )}
      </div>

      <div className="space-y-2 border-t p-3">
        {status.status === "Disabled" && <StatusNote tone="info">{t("an_off")}</StatusNote>}
        {status.status === "Quota Limited" && <StatusNote tone="warning">{t("an_quota_reached")}</StatusNote>}
        {nearLimit && (
          <p className="text-xs text-muted-foreground" data-testid="ai-usage">
            {t("an_quota_near", { used: status.usage.used, limit: status.usage.limit })}
          </p>
        )}
        <div className="flex gap-2 overflow-x-auto pb-1" role="group" aria-label={t("an_quick_actions")}>
          {status.actions.map((name) => (
            <button
              key={name}
              type="button"
              disabled={blocked}
              aria-pressed={action === name}
              onClick={() => onPick(name)}
              className={cn(
                "tap shrink-0 rounded-full border px-3 py-1 text-xs font-medium disabled:opacity-50",
                action === name ? "border-primary bg-primary text-primary-foreground" : "bg-background hover:bg-accent",
              )}
            >
              {ACTIONS[name] ? t(ACTIONS[name].label) : name}
            </button>
          ))}
        </div>
        {action && (
          <p className="flex items-center gap-1 text-xs text-muted-foreground">
            {t("an_using", { action: ACTIONS[action] ? t(ACTIONS[action].label) : action })}
            <button type="button" onClick={onClearAction} aria-label={t("an_clear_action")} className="rounded p-0.5 hover:bg-muted">
              <X className="size-3.5" aria-hidden />
            </button>
          </p>
        )}
        <form
          className="flex items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            onSend();
          }}
        >
          <div className="min-w-0 flex-1">
            <Label htmlFor="ask-question" className="sr-only">
              {t("an_your_question")}
            </Label>
            <Textarea
              id="ask-question"
              ref={box}
              rows={2}
              value={question}
              disabled={blocked}
              onChange={(e) => onQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
                  e.preventDefault();
                  onSend();
                }
              }}
              placeholder={t("an_placeholder")}
            />
          </div>
          <Button type="submit" disabled={blocked || !question.trim() || pending !== null} className="tap">
            <Send aria-hidden /> {t("an_send")}
          </Button>
        </form>
      </div>
    </section>
  );
}

function Bubble({ mine, children }: { mine?: boolean; children: ReactNode }) {
  return (
    <div className={cn("flex", mine ? "justify-end" : "justify-start")}>
      <div
        className={cn("max-w-[85%] rounded-2xl px-3.5 py-2.5 text-sm", mine ? "rounded-br-sm bg-primary text-primary-foreground" : "rounded-bl-sm bg-muted")}
      >
        {children}
      </div>
    </div>
  );
}

function Exchange({ item, variant, onRate }: { item: AiAnswer; variant: AssistantVariant; onRate: (id: number, rating: "Helpful" | "Not helpful") => void }) {
  const t = useT();
  const navigate = useNavigate();
  const refused = item.status === "Refused";
  const unanswered = !item.answered;

  return (
    <div className="space-y-2" data-testid="ai-exchange">
      <Bubble mine>
        <p className="whitespace-pre-wrap break-words">{item.question}</p>
      </Bubble>
      <Bubble>
        <div data-testid="ai-answer">
          {unanswered && (
            <p className="mb-1.5">
              <Tag tone="warning">{t("an_cant_answer")}</Tag>
            </p>
          )}
          <p className="whitespace-pre-wrap break-words">{item.answer}</p>
          {unanswered && variant === "student" && (
            <div className="mt-3">
              <p className="mb-2 text-xs text-muted-foreground">{t("an_ask_person")}</p>
              <Button
                size="sm"
                variant="outline"
                onClick={() =>
                  void navigate({ to: "/support", search: { new: 1, category: "Academic", subject: item.question.slice(0, 80), details: item.question } })
                }
              >
                <LifeBuoy aria-hidden /> {t("an_raise_support")}
              </Button>
            </div>
          )}
          {!refused && <Sources item={item} variant={variant} />}
          {item.warnings.length > 0 && (
            <ul className="mt-2 space-y-0.5 text-xs text-warning">
              {item.warnings.map((w) => (
                <li key={w}>⚠ {w}</li>
              ))}
            </ul>
          )}
          {!unanswered && (
            <div className="mt-3 flex items-center gap-2">
              <span className="text-xs text-muted-foreground">{t("an_helpful")}</span>
              <Button
                size="sm"
                variant={item.feedback === "Helpful" ? "default" : "outline"}
                onClick={() => onRate(item.ai_query_id, "Helpful")}
                aria-label={t("an_rate_up")}
              >
                <ThumbsUp aria-hidden />
              </Button>
              <Button
                size="sm"
                variant={item.feedback === "Not helpful" ? "default" : "outline"}
                onClick={() => onRate(item.ai_query_id, "Not helpful")}
                aria-label={t("an_rate_down")}
              >
                <ThumbsDown aria-hidden />
              </Button>
            </div>
          )}
        </div>
      </Bubble>
    </div>
  );
}

type Source = AiAnswer["sources"][number];

const SOURCE_NAME: Record<string, TranslationKey> = {
  enrolment: "an_src_course",
  class_session: "an_src_class",
  assignment: "an_src_assignment",
  test: "an_src_test",
  batch: "an_src_batch",
  curriculum_version: "an_src_outline",
};

/** Where an answer's facts came from, each one a link to the screen that shows it. */
function Sources({ item, variant }: { item: AiAnswer; variant: AssistantVariant }) {
  const t = useT();
  const unique = [...new Map(item.sources.map((s) => [`${s.type}-${s.code ?? s.id}`, s])).values()].slice(0, 6);
  if (unique.length === 0) return null;
  return (
    <div className="mt-3">
      <p className="text-xs font-semibold">{t("an_sources")}</p>
      <ul className="mt-1 flex flex-wrap gap-1.5 text-xs">
        {unique.map((source) => (
          <li key={`${source.type}-${source.code ?? source.id}`}>
            <SourceLink source={source} variant={variant} />
          </li>
        ))}
      </ul>
    </div>
  );
}

function SourceLink({ source, variant }: { source: Source; variant: AssistantVariant }) {
  const t = useT();
  const name = SOURCE_NAME[source.type];
  const text = `${name ? t(name) : source.type.replace("_", " ")} ${source.code ?? (source.id ? `#${source.id}` : "")}`.trim();
  const cls = "inline-block rounded-full border bg-background px-2 py-0.5 underline-offset-2 hover:bg-accent hover:underline";
  const id = source.id;
  if (variant === "trainer") {
    if (source.type === "batch")
      return (
        <Link to="/trainer/batches" className={cls}>
          {text}
        </Link>
      );
    if (source.type === "class_session")
      return (
        <Link to="/trainer/sessions" className={cls}>
          {text}
        </Link>
      );
    return <span className={cls}>{text}</span>;
  }
  if (id !== undefined) {
    if (source.type === "enrolment")
      return (
        <Link to="/courses/$enrolmentId" params={{ enrolmentId: String(id) }} className={cls}>
          {text}
        </Link>
      );
    if (source.type === "class_session")
      return (
        <Link to="/sessions/$sessionId" params={{ sessionId: String(id) }} className={cls}>
          {text}
        </Link>
      );
    if (source.type === "assignment")
      return (
        <Link to="/assignments/$id" params={{ id: String(id) }} className={cls}>
          {text}
        </Link>
      );
    if (source.type === "test")
      return (
        <Link to="/tests/$id" params={{ id: String(id) }} className={cls}>
          {text}
        </Link>
      );
  }
  if (source.type === "batch")
    return (
      <Link to="/schedule" className={cls}>
        {text}
      </Link>
    );
  if (source.type === "curriculum_version")
    return (
      <Link to="/my-courses" className={cls}>
        {text}
      </Link>
    );
  return <span className={cls}>{text}</span>;
}
