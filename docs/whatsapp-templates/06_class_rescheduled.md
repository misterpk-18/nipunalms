# 6. `nipuna_lms_class_rescheduled_u_v1`

| Field | Value |
|---|---|
| Category | Utility |
| Language | `en` |
| Header | None |
| Button | URL button **"Open schedule"**: `https://LMS_HOST/schedule` (static) |

## Body

```text
Hello {{1}}, Nipuna Technologies, {{2}}, has moved your class {{3}} for {{4}}. Old time: {{5}}. New time: {{6}}. Mode: {{7}}. Please check your Schedule page for the latest details.
```

| Variable | Meaning | Sample |
|---|---|---|
| `{{1}}` | Student name | `Anvitha K.` |
| `{{2}}` | Branch name | `Guntur` |
| `{{3}}` | Class title | `Hyperparameter Tuning` |
| `{{4}}` | Course name | `Data Science & Applied AI` |
| `{{5}}` | Old start, day and time in IST | `Mon 12 Oct, 10:00 AM IST` |
| `{{6}}` | New start, day and time in IST | `Wed 14 Oct, 2:00 PM IST` |
| `{{7}}` | Mode and place at the new time | `Live Online` |

## When the LMS sends it

- **Trigger.** A class's start time changes: either an approved reschedule request, or a direct move by the Branch Manager.
- **Not sent** when only the trainer, room or Meet link changes and the time stays the same. The app shows those details.
- **One message per move.** Several moves of the same class each send one message, for the latest time.
- **Dedupe key.** `class-rescheduled:<session id>:<student id>:<new start time>`.
- **Reminders.** The class reminder (template 4) then follows the new time.
