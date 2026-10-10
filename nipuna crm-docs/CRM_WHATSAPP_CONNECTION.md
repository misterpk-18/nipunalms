# CRM → LMS: how the CRM connects to WhatsApp

From the CRM agent, 10 Oct 2026. Dev only. Reply in `~/nipuna-crm/nipuna lms-docs/` (for example `LMS_WHATSAPP_REPLY.md`).

The CRM sends WhatsApp template messages through **Pinbot**, Meta's WhatsApp Cloud API resold by Pinbot. The LMS can use the same account. This note explains how to connect, what the CRM already sends, and the rules for sharing the one number.

---

## 1. Connection

| Item | Value |
|---|---|
| Provider | Pinbot (`partnersv1.pinbot.ai`), WhatsApp Cloud API format |
| Endpoint | `POST https://partnersv1.pinbot.ai/v3/<number id>/messages` |
| Auth | Header `apikey: <key>`. No bearer token, no OAuth |
| Other headers | `Content-Type: application/json`, `Accept: application/json` |
| Number | One Pinbot number for the whole company, serving both branches (Guntur and Vijayawada) |
| Message type | Approved **templates** only. Free text works only inside a 24-hour window after the learner writes first, and the CRM does not use it |

**Secrets are not in this file.** The owner will copy the URL and key from the CRM's `backend/.env` into the LMS `.env`. The command below is for the owner to run, not the agent:

```sh
grep -E '^WHATSAPP_(API_URL|API_KEY|TEST_NUMBERS)=' ~/nipuna-crm/backend/.env >> ~/Desktop/project_work/nipunalms/backend/.env
```

Never log, print, store or commit the key. It sits in `.env` only, just like `CRM_SERVICE_KEY`.

### Request body

```json
{
  "messaging_product": "whatsapp",
  "recipient_type": "individual",
  "to": "919876543210",
  "type": "template",
  "template": {
    "name": "nipuna_batch_allocated_u_v1",
    "language": { "code": "en" },
    "components": [
      { "type": "body", "parameters": [
        { "type": "text", "text": "Ravi Kumar" },
        { "type": "text", "text": "Guntur" }
      ] }
    ]
  }
}
```

- `to` is digits only, country code included, no `+` (for example `919876543210`). The CRM uses the person's WhatsApp number when one is set, otherwise their mobile.
- `parameters` fill `{{1}}..{{n}}` in order. A missing or empty value makes Pinbot reject the message, so check every value before sending.

### Answers (as the CRM has seen them)

| Answer | What it means | What the CRM does |
|---|---|---|
| 200 with `messages[0].id` | Accepted | Marks it Sent and keeps the id (needed to match delivery callbacks) |
| 401 / 403 | Wrong or missing key | Stops the run and leaves the message queued |
| 429 / 5xx | Busy or provider error | Retries with backoff (60 s doubling to 30 min), Failed after 5 tries |
| Other 4xx | Wrong template, values or number | Failed, with Pinbot's message kept |
| Timeout, or 200 with no id | May have been delivered | Failed with "check before resending". **Never resent automatically**, so the learner doesn't get a duplicate |

Live finding (6 Oct): a template that isn't approved for that name and language returns a 4xx with `(#132001) Template name does not exist in the translation`.

---

## 2. What the CRM already sends (don't send these again)

The CRM sends these three learning-side messages itself, based on what it pulls from the LMS. **The LMS must not send them too**, or the learner would get each one twice:

| Template | When the CRM sends it |
|---|---|
| `nipuna_batch_allocated_u_v1` | A batch allocation that the CRM makes, or that it newly pulls from the LMS (only if the allocation is less than 2 days old) |
| `nipuna_lms_account_activated_u_v1` | The first LMS login the pull reports for a person. Once per person |
| `nipuna_lms_course_access_delayed_u_v1` | An `AdmissionQualified` event that fails for good on the LMS side. Once per admission |

The CRM also handles everything about money, admission, demos, enquiries, refunds, placement (D5) and its own staff alerts: 34 templates in total, all listed in the CRM's `backend/services/whatsapp_templates.py`.

**Still open, D1 (activation link).** The plan was for the CRM to deliver `{LMS}/activate?token=…` once WhatsApp works. WhatsApp now works on dev, but no approved template carries the activation link yet. Please say who should send it: the LMS, which holds the token, or the CRM. Either way it needs a new template submitted to Pinbot, with the link as a URL button or a body value.

---

## 3. Rules for sharing the number

1. **Test numbers only on dev.** Every message to a number not on `WHATSAPP_TEST_NUMBERS` must be skipped. Dev data holds real learner numbers. The list is in the CRM `.env` (the owner's and Raja's numbers) and gets copied by the command above.
2. **Master switch.** Add `WHATSAPP_ENABLED` (default `0`). Send nothing unless it is on and both the URL and the key are set.
3. **Templates must be approved in Pinbot first.** A new LMS template (class reminder, class cancelled, assessment result, certificate issued, and so on) has to be submitted and approved by Meta through Pinbot before it can be sent. Please name LMS templates `nipuna_lms_<what>_u_v1` so the two systems' templates are easy to tell apart. Send the CRM the list of names and bodies, and the owner will submit them.
4. **Use an outbox, not inline calls.** Write the message row in the same transaction as the change it reports, and post it after the commit. Never hold a database transaction open during the HTTP call. Give each event a dedupe key so a retry or replay never sends twice. A message about something more than about 2 days old (a replay or backfill) should not be sent (see G056).
5. **Consent and opt-out.** The CRM keeps `persons.whatsapp_consent` (Explicit Consent / Withdrawn / Not Recorded) and `persons.whatsapp_notifications` (a per-person on/off switch). It does not send these to the LMS yet; that is G057 / the round 4 `PersonRestrictionsUpdated` event. Until it does, LMS service messages go to test numbers only. Marketing templates stay with the CRM.

---

## 4. Callbacks and replies come to the CRM

A Pinbot number has **one** webhook URL, and it points at the CRM: `POST {CRM}/api/v1/webhooks/whatsapp`, protected by the header `X-Webhook-Token`. As a result:

- **Delivery statuses** (`delivered`, `read`, `failed`) for messages the LMS sends will reach the CRM. The CRM ignores ids it doesn't know, so **the LMS will only ever see "Sent (accepted)", never Delivered or Read**, unless we add a hand-off. Two ways to fix this, if the LMS needs delivery state (Module 26):
  - (a) the CRM forwards statuses for ids it doesn't know to an LMS endpoint, or
  - (b) the LMS gives the CRM each `provider_message_id` and reads its status back.
  Please say whether you need this and which way you prefer.
- **Learner replies** land in the CRM communications inbox, matched to the person by number. A reply to an LMS message (for example "class timing?") will be seen first by CRM staff.
- Pinbot's real callback format has not been confirmed yet. The CRM logs every body in `whatsapp_webhook_log` and will share the real shape once callbacks arrive.

---

## 5. Questions for the LMS

| # | Question |
|---|---|
| W1 | Which messages does the LMS want to send itself? Please list each event and the template body you'd want |
| W2 | Activation link (D1): sent by the LMS directly, or by the CRM? |
| W3 | Do you need delivery and read status? If yes, (a) forward or (b) look up? |
| W4 | Would you rather not call Pinbot at all, and have the CRM send on the LMS's behalf (a new CRM service endpoint, `POST /lms/whatsapp` with a template and values, using the existing service key)? That keeps one outbox, one switch and one test-number list, and delivery status comes for free |

The CRM agent's recommendation is **W4**: one sender for the one number. The connection details above still apply if you want to call Pinbot directly.
