# 7. `nipuna_lms_result_published_u_v1`

| Field | Value |
|---|---|
| Category | Utility |
| Language | `en` |
| Header | None |
| Button | URL button **"View result"**: `https://LMS_HOST/progress?tab=results` (static) |

## Body

```text
Hello {{1}}, Nipuna Technologies, {{2}}, has published your result for {{3}} in {{4}}. You can see your marks and your trainer's feedback under My Progress in your learning account.
```

| Variable | Meaning | Sample |
|---|---|---|
| `{{1}}` | Student name | `Anvitha K.` |
| `{{2}}` | Branch name | `Guntur` |
| `{{3}}` | Assessment or assignment title | `Module 3 test: Regression` |
| `{{4}}` | Course name | `Data Science & Applied AI` |

Marks and pass/fail are left out on purpose: they are private and can change if a result is corrected.

## When the LMS sends it

- **Trigger.** The Branch Manager publishes results for a formal assessment or a marked assignment. Each student with a newly published result gets one message.
- **Not sent** for practice quizzes (their score shows at once in the app) or for provisional marks.
- **Batching.** Publishing several assessments at once still sends one message per student per assessment, so keep publishing deliberate.
- **Dedupe key.** `result-published:<result id>:<published version>`. A later correction sends again only if the result is re-published.
