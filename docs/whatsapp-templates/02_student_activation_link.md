# 2. `nipuna_lms_student_activation_link_u_v1`

| Field | Value |
|---|---|
| Category | Utility |
| Language | `en` |
| Header | None |
| Button | URL button **"Activate account"**: `https://LMS_HOST/activate?token={{1}}` |

## Body

```text
Hello {{1}}, Nipuna Technologies, {{2}}, has created your learning account. Your Student ID is {{3}}. Tap Activate account below to set your own password. The link works once and expires on {{4}}. If you did not expect this message, please contact your branch.
```

| Variable | Meaning | Sample |
|---|---|---|
| `{{1}}` | Student name | `Anvitha K.` |
| `{{2}}` | Branch name | `Guntur` |
| `{{3}}` | Student ID (they sign in with it) | `NIT-STU-2026-004182` |
| `{{4}}` | Link expiry, date and time in IST | `13 Oct 2026, 6:00 PM IST` |
| Button `{{1}}` | The one-time activation token | `kQ3v9xZp2LmN8rT4` |

## When the LMS sends it

- **Trigger.** Staff press "Send new link" on Student Accounts, or the first link is issued after `AdmissionQualified`. This answers the CRM's open item D1: the LMS holds the token, so the LMS sends the link.
- **Copy fallback.** "Copy link" stays on the screen as a fallback for students without WhatsApp.
- **Reissue.** Issuing a new link cancels the previous one, so only the newest message works.
- **Dedupe key.** `activation-link:<activation token id>`.
- **Not sent** to students who are already activated.
