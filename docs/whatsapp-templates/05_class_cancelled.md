# 5. `nipuna_lms_class_cancelled_u_v1`

| Field | Value |
|---|---|
| Category | Utility |
| Language | `en` |
| Header | None |
| Button | URL button **"Open schedule"**: `https://LMS_HOST/schedule` (static) |

## Body

```text
Hello {{1}}, Nipuna Technologies, {{2}}, has cancelled your class {{3}} for {{4}} that was planned for {{5}}. Reason: {{6}}. What happens next: {{7}}. This cancellation is not marked as an absence. Please check your Schedule page for updates.
```

| Variable | Meaning | Sample |
|---|---|---|
| `{{1}}` | Student name | `Anvitha K.` |
| `{{2}}` | Branch name | `Guntur` |
| `{{3}}` | Class title | `Hyperparameter Tuning` |
| `{{4}}` | Course name | `Data Science & Applied AI` |
| `{{5}}` | Planned start, day and time in IST | `Mon 12 Oct, 10:00 AM IST` |
| `{{6}}` | Reason in plain words | `the trainer is unwell` |
| `{{7}}` | Next step | `a replacement class will be scheduled and shared with you` / `no replacement is needed because this topic is covered in the next class` |

## When the LMS sends it

- **Trigger.** A class is cancelled, either by the Branch Manager or by an approved emergency cancellation.
- **Who gets it.** Every student holding a seat in the class's batch (or batches).
- **Not sent** for a class that has already happened, or one more than 2 days in the past.
- **Dedupe key.** `class-cancelled:<session id>:<student id>`.
