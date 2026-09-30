/** Ask Nipuna: the student study assistant and the staff assistant. Shows scope, sources, warnings and the daily allowance. */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Send, ThumbsDown, ThumbsUp } from "lucide-react";
import { askApi, type AiAnswer } from "@/api/ask-nipuna";
import { Note, PageHead, QueryView, Section, StatusBadge, StatusNote } from "@/components/lms/ui";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useApiMutation } from "@/lib/mutation";
import { fmtDateTime } from "@/features/shared/format";

const BLOCKED: Record<string, string> = {
  "Quota Limited": "Daily limit reached. It resets at 00:00 IST.",
  Disabled: "Assistant disabled by an administrator. Your studies and classes are not affected.",
};

export function Assistant({ title }: { title: string }) {
  const [question, setQuestion] = useState("");
  const [latest, setLatest] = useState<AiAnswer | null>(null);
  const status = useQuery({ queryKey: ["ask", "status"], queryFn: askApi.status });
  const history = useQuery({ queryKey: ["ask", "history"], queryFn: () => askApi.history() });
  const ask = useApiMutation((vars: { question: string; action?: string }) => askApi.ask(vars.question, vars.action), {
    invalidate: [["ask"]],
    onSuccess: (answer) => {
      setLatest(answer);
      setQuestion("");
    },
  });
  const feedback = useApiMutation((vars: { id: number; rating: "Helpful" | "Not helpful" }) => askApi.feedback(vars.id, vars.rating), {
    invalidate: [["ask"]],
    success: "Thanks for the feedback",
    onSuccess: (updated) =>
      setLatest((current) => (current && current.ai_query_id === updated.ai_query_id ? { ...current, feedback: updated.feedback } : current)),
  });

  return (
    <div className="mx-auto max-w-5xl">
      <QueryView query={status}>
        {(s) => {
          const blocked = s.status === "Quota Limited" || s.status === "Disabled";
          const submit = (action?: string) => {
            const text = question.trim() || action || "";
            if (text) ask.mutate({ question: text, ...(action ? { action } : {}) });
          };
          return (
            <>
              <PageHead
                title={title}
                description={`${s.audience} assistant · advisory only · ${s.mode === "ai" ? "AI-written answers" : "answers from your records, no AI provider connected"}`}
              />
              <Section className="mb-4">
                <div className="flex flex-wrap items-center gap-2 text-sm">
                  <StatusBadge tone={s.status === "AI Available" ? "success" : s.status === "Configuration Pending" ? "warning" : "danger"}>
                    {s.status}
                  </StatusBadge>
                  <span>
                    Usage today (IST):{" "}
                    <strong data-testid="ai-usage">
                      {s.usage.used} / {s.usage.limit}
                    </strong>{" "}
                    answers · resets at 00:00 IST
                  </span>
                </div>
                <p className="mt-2 text-sm">{s.scope_note}</p>
              </Section>
              <div className="grid gap-4 lg:grid-cols-3">
                <Section title="Ask" className="lg:col-span-2">
                  <div className="mb-3 flex flex-wrap gap-2">
                    {s.actions.map((action) => (
                      <Button key={action} variant="outline" disabled={blocked || ask.isPending} onClick={() => submit(action)}>
                        {action}
                      </Button>
                    ))}
                  </div>
                  <Label htmlFor="ask-question">Your question</Label>
                  <Textarea
                    id="ask-question"
                    rows={3}
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    placeholder="e.g. When is my next class? / నా తదుపరి తరగతి ఎప్పుడు?"
                  />
                  <div className="mt-2">
                    <Button disabled={blocked || ask.isPending || !question.trim()} onClick={() => submit()}>
                      <Send aria-hidden /> Ask
                    </Button>
                  </div>
                  {blocked && (
                    <div className="mt-3">
                      <StatusNote state="Permission Restricted">{BLOCKED[s.status]}</StatusNote>
                    </div>
                  )}
                  {latest && <AnswerCard answer={latest} onRate={(rating) => feedback.mutate({ id: latest.ai_query_id, rating })} />}
                </Section>
                <Section title="Earlier answers">
                  <QueryView query={history} isEmpty={(h) => h.data.length === 0} empty="Nothing asked yet.">
                    {(h) => (
                      <ul className="space-y-2 text-sm">
                        {h.data.map((item) => (
                          <li key={item.ai_query_id}>
                            <button className="w-full rounded-lg border p-2 text-left hover:bg-muted" onClick={() => setLatest(item)}>
                              <span className="block truncate font-medium">{item.question}</span>
                              <span className="text-xs text-muted-foreground">
                                {fmtDateTime(item.created_at)} · {item.status}
                              </span>
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </QueryView>
                </Section>
              </div>
              <div className="mt-4">
                <Note>
                  Answers are advisory. Ask Nipuna never awards marks, attendance, completion or certificates, and never shows another person&apos;s data.
                </Note>
              </div>
            </>
          );
        }}
      </QueryView>
    </div>
  );
}

function AnswerCard({ answer, onRate }: { answer: AiAnswer; onRate: (rating: "Helpful" | "Not helpful") => void }) {
  const refused = answer.status === "Refused";
  return (
    <div className="mt-4 rounded-lg border bg-muted p-3 text-sm" aria-live="polite" data-testid="ai-answer">
      <div className="flex flex-wrap items-center gap-2">
        <StatusBadge tone={refused ? "warning" : answer.is_fallback ? "neutral" : "info"}>
          {refused ? "Not answered: out of scope" : answer.is_fallback ? "Answered from your records (rule-based)" : "AI-written answer"}
        </StatusBadge>
        <span className="text-xs text-muted-foreground">Q: {answer.question}</span>
      </div>
      <p className="mt-2 whitespace-pre-wrap break-words">{answer.answer}</p>
      {!refused && (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          <div>
            <p className="text-xs font-semibold">Sources / evidence</p>
            {answer.sources.length === 0 ? (
              <p className="text-xs">No records were needed.</p>
            ) : (
              <ul className="list-disc pl-4 text-xs">
                {[...new Map(answer.sources.map((s) => [`${s.type}-${s.code ?? s.id}`, s])).values()].slice(0, 8).map((s) => (
                  <li key={`${s.type}-${s.code ?? s.id}`}>
                    {s.type.replace("_", " ")} {s.code ?? `#${s.id}`}
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div>
            <p className="text-xs font-semibold">Scope</p>
            <p className="text-xs">{answer.scope_note}</p>
          </div>
        </div>
      )}
      {answer.warnings.length > 0 && (
        <ul className="mt-2 space-y-0.5 text-xs text-warning">
          {answer.warnings.map((w) => (
            <li key={w}>⚠ {w}</li>
          ))}
        </ul>
      )}
      {!refused && (
        <div className="mt-3 flex items-center gap-2">
          <span className="text-xs">Was this helpful?</span>
          <Button size="sm" variant={answer.feedback === "Helpful" ? "default" : "outline"} onClick={() => onRate("Helpful")} aria-label="Helpful">
            <ThumbsUp aria-hidden />
          </Button>
          <Button size="sm" variant={answer.feedback === "Not helpful" ? "default" : "outline"} onClick={() => onRate("Not helpful")} aria-label="Not helpful">
            <ThumbsDown aria-hidden />
          </Button>
        </div>
      )}
    </div>
  );
}
