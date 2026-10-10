# 8. `nipuna_lms_certificate_issued_u_v1`

| Field | Value |
|---|---|
| Category | Utility |
| Language | `en` |
| Header | None |
| Button | URL button **"Verify certificate"**: `https://LMS_HOST/verify/{{1}}` |

## Body

```text
Hello {{1}}, Nipuna Technologies, {{2}}, has issued your {{3}} for {{4}}. Certificate number: {{5}}. You can download it from Certificates in your learning account, and anyone can check it with the Verify certificate link below.
```

| Variable | Meaning | Sample |
|---|---|---|
| `{{1}}` | Student name | `Anvitha K.` |
| `{{2}}` | Branch name | `Guntur` |
| `{{3}}` | Certificate type | `Course Completion Certificate` / `Internship Certificate` |
| `{{4}}` | Course name | `Data Science & Applied AI` |
| `{{5}}` | Certificate number | `NIT-CERT-2026-000123` |
| Button `{{1}}` | Certificate number (public verification page) | `NIT-CERT-2026-000123` |

## When the LMS sends it

- **Trigger.** A certificate is issued for the first time, or a corrected version is issued. The body stays the same; the verification page shows the current version.
- **Not sent** for revocations or reinstatements. Those are handled by staff with the student directly. Add a separate template later if needed.
- **Dedupe key.** `certificate-issued:<certificate id>:<version>`.
