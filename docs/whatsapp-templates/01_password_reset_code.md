# 1. `nipuna_lms_password_reset_code_auth_v1`

| Field | Value |
|---|---|
| Category | **Authentication** (Meta's one-time-code category, not Utility) |
| Language | `en` |
| Header | None |
| Body | Fixed by Meta (see below); you only choose the options |
| Options | Security recommendation **on**; code expiry **10 minutes** |
| Button | **Copy code** (one-tap copy) |

## What the learner receives

Meta builds the text from the options. With the options above it reads:

```text
*{{1}}* is your verification code. For your security, do not share this code.
This code expires in 10 minutes.
```

| Variable | Meaning | Sample |
|---|---|---|
| `{{1}}` | The 6-digit reset code (also filled into the Copy code button) | `482913` |

## When the LMS sends it

- **Trigger.** On the sign-in page, a student (by Student ID or email) or a staff user asks "Forgot password? Send me a code". The code goes to the WhatsApp number on file, falling back to email when the person has one.
- **The code.** It is single use and expires after 10 minutes. Only its hash is stored. At most 5 codes per person per hour.
- **What the page shows.** It always says "If the account exists, we've sent a code", so it never reveals whether an account exists.
- **Dedupe key.** `pwd-reset:<user id>:<code request id>`. The code is never resent automatically on a timeout.
