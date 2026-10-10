# 4. `nipuna_lms_class_reminder_u_v1`

| Field | Value |
|---|---|
| Category | Utility |
| Language | `en` |
| Header | None |
| Button | URL button **"Open schedule"**: `https://LMS_HOST/schedule` (static) |

## Body

```text
Hello {{1}}, this is a reminder from Nipuna Technologies, {{2}}. Your class {{3}} for {{4}} starts at {{5}}. Mode: {{6}}. Please be on time; the Join button opens 15 minutes before the start on your Schedule page.
```

| Variable | Meaning | Sample |
|---|---|---|
| `{{1}}` | Student name | `Anvitha K.` |
| `{{2}}` | Branch name | `Guntur` |
| `{{3}}` | Class title (the topic, or the session title) | `Hyperparameter Tuning` |
| `{{4}}` | Course name | `Data Science & Applied AI` |
| `{{5}}` | Start, day and time in IST | `Mon 12 Oct, 10:00 AM IST` |
| `{{6}}` | Mode and place | `Live Online` / `Classroom, Lab 2, Guntur` |

## When the LMS sends it

- **Trigger.** A scheduled job sends it once per student per confirmed class, about 2 hours before the start. If a class is confirmed inside that window, the job sends it at once, provided the class is still more than 15 minutes away.
- **Who gets it.** Students with an active seat in the class's batch (or batches, for a shared class).
- **Not sent** for cancelled classes, classes already started, or students who switched class reminders off in Profile.
- **Dedupe key.** `class-reminder:<session id>:<student id>:<start time>`. A rescheduled class gets a fresh reminder for its new time.
