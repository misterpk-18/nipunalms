# 3. `nipuna_lms_staff_account_invite_u_v1`

| Field | Value |
|---|---|
| Category | Utility |
| Language | `en` |
| Header | None |
| Button | URL button **"Set password"**: `https://LMS_HOST/activate?token={{1}}` |

## Body

```text
Hello {{1}}, a Nipuna Technologies LMS staff account has been created for you as {{2}} at {{3}}. You will sign in with your email address. Tap Set password below to choose your password. The link works once and expires on {{4}}. If you were not expecting this, please tell your Super Admin.
```

| Variable | Meaning | Sample |
|---|---|---|
| `{{1}}` | Staff member's name | `Ravi Kumar` |
| `{{2}}` | Role | `Branch Manager` |
| `{{3}}` | Branch, or "all branches" for company-wide roles | `Guntur` |
| `{{4}}` | Link expiry, date and time in IST | `13 Oct 2026, 6:00 PM IST` |
| Button `{{1}}` | The one-time activation token | `pL7wQ2nX9vR4tK8m` |

## When the LMS sends it

- **Trigger.** A Super Admin creates a staff user, or presses "Resend invite". This replaces handing over a temporary password by word of mouth.
- **Fallback.** The temporary password stays available when the person has no WhatsApp number.
- **Dedupe key.** `staff-invite:<activation token id>`.
- **Not sent** to users who have already set a password.
