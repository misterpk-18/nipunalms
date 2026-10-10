# Working rules for Claude in this repo

## Questions: selectable options only (strict)

- **Never ask a question as free text in a reply.** Every question to the user goes through the `AskUserQuestion` tool, so the user can always pick an option.
- This covers all questions: blockers mid-task, clarifications, choices between approaches, and follow-ups at the end of a task. A trailing "want me to…?" in prose is not allowed either.
- Give 2–4 concrete options per question and put the recommended one first, labelled "(Recommended)". Batch related questions into one call.
- If a question has no sensible options or a conventional default exists, do not ask in prose: choose the default and state it in the reply.
- If `AskUserQuestion` is unavailable, say so and stop; do not fall back to free-text questions.
