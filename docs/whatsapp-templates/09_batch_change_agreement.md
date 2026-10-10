# 9. `nipuna_lms_batch_change_agreement_u_v1`

| Field | Value |
|---|---|
| Category | Utility |
| Language | `en` |
| Header | None |
| Button | URL button **"Respond"**: `https://LMS_HOST/dashboard` (static; Home shows the change with Agree / Decline) |

## Body

```text
Hello {{1}}, Nipuna Technologies, {{2}}, proposes a change to your batch for {{3}}. Now: {{4}}. Proposed: {{5}}. Reason: {{6}}. Please open your learning account and choose Agree or Decline by {{7}}. Nothing changes for you until you answer.
```

| Variable | Meaning | Sample |
|---|---|---|
| `{{1}}` | Student name | `Anvitha K.` |
| `{{2}}` | Branch name | `Guntur` |
| `{{3}}` | Course name | `Data Science & Applied AI` |
| `{{4}}` | Current arrangement, short | `Mon and Wed, 10:00 AM to 12:00 PM, Hybrid` |
| `{{5}}` | Proposed arrangement, short | `Mon and Wed, 2:00 PM to 4:00 PM, from 2 Nov` |
| `{{6}}` | Reason in plain words | `the lab is needed for a new morning batch` |
| `{{7}}` | Reply-by date | `20 Oct 2026` |

The "If you do not agree" alternative is left out of the message to keep it short. Home shows it next to the Agree / Decline buttons.

## When the LMS sends it

- **Trigger.** The Branch Manager records a material batch change (days, times, mode, location, trainer model) that needs each student's agreement.
- **Who gets it.** Every student holding a seat in that batch.
- **Reminder.** One reminder may be sent 2 days before the reply-by date to students who haven't answered. The reminder uses the same template with the same values.
- **Not sent** once the student has answered, or after the change is withdrawn.
- **Dedupe key.** `batch-change:<change id>:<student id>`, or `batch-change:<change id>:<student id>:reminder` for the reminder.
