# LMS WhatsApp templates (drafts to submit in Pinbot)

These are the WhatsApp messages the LMS itself will send. Each file holds one template: name, category, body, buttons,
the meaning and a sample value for every `{{n}}`, and when the LMS sends it. **None is submitted yet.** The owner submits
them in Pinbot (Meta approval), then the LMS can send them through the CRM (W4 in
`nipuna crm-docs/CRM_WHATSAPP_CONNECTION.md`). The LMS side is **built and switched off** (UX phase U6, [API.md §4.13](../API.md)): templates 4–9 are wired and
named in `backend/services/whatsapp_templates.py`; 1–3 follow with sign-in (U7). Once a template is approved, add its name to
`app_settings.whatsapp_approved_templates`.

## The templates

| # | Template name | Category | Who gets it | When | Button |
|---|---|---|---|---|---|
| 1 | [`nipuna_lms_password_reset_code_auth_v1`](01_password_reset_code.md) | Authentication | Student or staff | They ask for a password reset code on the sign-in page | Copy code |
| 2 | [`nipuna_lms_student_activation_link_u_v1`](02_student_activation_link.md) | Utility | Student | Staff issue or reissue an activation link | Activate account (link) |
| 3 | [`nipuna_lms_staff_account_invite_u_v1`](03_staff_account_invite.md) | Utility | New staff user | Super Admin creates a staff account (or resends the invite) | Set password (link) |
| 4 | [`nipuna_lms_class_reminder_u_v1`](04_class_reminder.md) | Utility | Student | Before each confirmed class | Open schedule (link) |
| 5 | [`nipuna_lms_class_cancelled_u_v1`](05_class_cancelled.md) | Utility | Student | A class is cancelled | Open schedule (link) |
| 6 | [`nipuna_lms_class_rescheduled_u_v1`](06_class_rescheduled.md) | Utility | Student | A class moves to a new time | Open schedule (link) |
| 7 | [`nipuna_lms_result_published_u_v1`](07_result_published.md) | Utility | Student | A formal result is published | View result (link) |
| 8 | [`nipuna_lms_certificate_issued_u_v1`](08_certificate_issued.md) | Utility | Student | A certificate is issued (first issue or a corrected version) | Verify certificate (link) |
| 9 | [`nipuna_lms_batch_change_agreement_u_v1`](09_batch_change_agreement.md) | Utility | Student | A material batch change needs the student's Agree / Decline | Respond (link) |

## Not sent by the LMS (the CRM already sends them)

Don't create LMS versions of these. The learner would get each one twice:

- `nipuna_batch_allocated_u_v1`
- `nipuna_lms_account_activated_u_v1`
- `nipuna_lms_course_access_delayed_u_v1`

## Conventions (same as the CRM's 34 templates)

- **Names.** Names follow `nipuna_lms_<what>_<category>_v1`. The category part is `_u_` for Utility, as in the CRM. The reset code uses `_auth_` because Meta files OTPs under the separate **Authentication** category.
- **Language.** English (`en`) only for now, like every CRM template. A Telugu version would be a second template with the same name and language `te`, submitted later.
- **Body style.** Bodies open with "Hello {{1}}, Nipuna Technologies, {{2}}," (learner name, branch name). They state one fact and then what to do next. They contain no marks, amounts or other private details. The learner reads those in the app.
- **Meta rules the drafts already follow:**
  - The body never starts or ends with a variable.
  - No variable value may be empty or contain a line break.
  - There is enough fixed text around the variables.
  - Bodies stay under 1,024 characters.
- **Sample values.** Meta asks for one sample per variable at submission. Use the sample column in each file.
- **Button links.** Every link points to the LMS host, written here as `https://LMS_HOST`. **Replace `LMS_HOST` with the real LMS domain before submitting.** The base URL is fixed at approval, and only the part after it (`{{1}}`) changes per message. A static link (no variable) needs only the full URL.

## Before submitting (checklist for the owner)

1. Replace `LMS_HOST` in every button with the production LMS domain.
2. In Pinbot, create each template with the exact name, category, language, body and buttons from its file, and enter the sample values.
3. For template 1, choose the **Authentication** category, turn on the security recommendation and a 10-minute expiry, and pick the **Copy code** button. The body text is fixed by Meta, so you only set those options.
4. When a template is approved, put its name in the LMS setting `whatsapp_approved_templates` (a JSON list in `app_settings`). Only approved names are sent; the reply to the CRM (W1) already lists all nine.

## Sending rules the LMS will follow (from the CRM's note)

- **Through the CRM.** The LMS sends through the CRM's endpoint (W4): one number, one outbox, one on/off switch, one test-number list. Delivery and read status come back through the CRM.
- **Dev safety.** On dev, numbers not on the test-number list are skipped. Until the CRM sends consent and opt-out data (G057 / `PersonRestrictionsUpdated`), class, result, certificate and batch-change messages go to test numbers only. Account messages (1–3) are service messages the person asked for.
- **No duplicates.**
  - Each message carries a dedupe key, listed in each file, so a retry or replay never sends twice.
  - A message about something more than 2 days old is not sent.
  - Reset codes expire in 10 minutes and are never resent automatically.
- **Learner replies.** Replies go to the CRM inbox, because the number's webhook points there. Bodies therefore point learners to the app, not to "reply to this message".
