# Meta template forms to resubmit: activation link and staff invite

Pinbot's template report (28 Oct 2026) shows two LMS templates **Rejected**: `nipuna_lms_student_activation_link_u_v1` and `nipuna_lms_staff_account_invite_u_v1`. Both were submitted on 24 Oct. The rejection reason is not in the report. **Read it in the Pinbot or Meta panel before resubmitting**, and fix that first; the drafts below fix the usual causes but cannot know yours.

## Most likely causes, in order

1. **The button's website address.** Both templates have a "Set password / Activate account" URL button. Meta checks the domain. On 24 Oct the LMS had no real address, and the one now live (`3-111-225-125.sslip.io`) is an IP-based free domain that Meta may also refuse. Resubmit with the LMS's own hostname once it exists (for example `lms.nipunacareers.com` or a nipunatechnologies.com name). The button is a dynamic URL ending in the token: `https://<LMS host>/activate?token={{1}}`.
2. **A missing or unusable sample** for a variable or for the button.
3. **Wording** that reads as an account or security message when filed as Utility, or has a variable at the very start or end of a sentence with too little text around it.

## What changes in code on approval

Only the **names** and the **body text**. The variables keep their order and meaning, so no code for building the message changes. When Meta approves a version:
- LMS: rename the template in `backend/services/whatsapp_templates.py` and add the new name to `whatsapp_approved_templates`.
- CRM: rename it in its registry (`services/whatsapp_templates.py`) in the same release, and the CRM team confirms.
Do not rename before approval: a name Pinbot does not know is refused, as the v1 names are now.

---

## 1. `nipuna_lms_student_activation_link_u_v2`

* **Category:** Utility
* **Language:** English (`en`)
* **Body:**
  ```text
  Hello {{1}}, your Nipuna Technologies learning account at {{2}} is ready. Your Student ID is {{3}}. Use the button below to set your password. This link can be used once and expires on {{4}}. If you were not expecting this, please contact your branch.
  ```
* **Samples:** `{{1}}` Anvitha K. · `{{2}}` Guntur · `{{3}}` NIT-STU-2026-000001 · `{{4}}` 30 Oct 2026
* **Button:** Visit website, dynamic URL, text **Activate account**, URL `https://<LMS host>/activate?token={{1}}`, sample `7f3a9c1e2b`

## 2. `nipuna_lms_staff_account_invite_u_v2`

* **Category:** Utility
* **Language:** English (`en`)
* **Body:**
  ```text
  Hello {{1}}, your Nipuna Technologies LMS account has been created with the role {{2}} at {{3}}. Use the button below to choose your password. This link can be used once and expires on {{4}}. If you were not expecting this, please tell your Super Admin.
  ```
* **Samples:** `{{1}}` Ravi Kumar · `{{2}}` Branch Manager · `{{3}}` Guntur · `{{4}}` 30 Oct 2026
* **Button:** Visit website, dynamic URL, text **Set password**, URL `https://<LMS host>/activate?token={{1}}`, sample `7f3a9c1e2b`

---

## Until they are approved

Both messages go **by email only**. A student's activation link can also be copied or reissued by a Branch Manager on Student Accounts. The combined test plan treats their WhatsApp as Skipped.
