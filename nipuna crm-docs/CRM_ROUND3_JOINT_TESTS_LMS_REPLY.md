# LMS → CRM: round 3 joint tests, go-ahead

**From:** the `nipunalms` side. **For:** whoever works on `nipuna-crm` (a developer or a Claude Code session in the CRM repo).
**Answers:** [CRM_ROUND3_JOINT_TESTS.md](CRM_ROUND3_JOINT_TESTS.md) §2 ("Please reply with").
**Date:** 2026-10-02. Local only: CRM `nipunacrm-dev` on :5050 ↔ LMS `nipunalms-dev` on :5060.

**In short:** the LMS owner approved the whole script on `NIT-CRS-007`. **Step 1 is done.** `CV 4.2` is ready for step
3, and the LMS will activate it only when you ask. You can start step 2 now.

---

## 1. Your three questions

| # | Answer |
|---|---|
| 1 | **Go-ahead: yes.** `CV 4.1` and `CV 4.2` on `NIT-CRS-007` are approved, knowing `CV 4.0` and `CV 4.1` end up Retired |
| 2 | **Admission Y: yes.** Create it through the normal invoice → verified payment flow. The LMS auto-maps it to whatever is Active when its `AdmissionQualified` arrives |
| 3 | **Outage window: on request.** When you are at step 6, tell the LMS side. It stops `:5060` for about 60 s, starts it again, and confirms your event was Applied. There is no fixed time; any time today works |

Test 6 doesn't need a live run; both automated suites cover it, as you suggest.

## 2. Where the script stands

| Step | Status (2026-10-02, 21:35 IST) |
|---|---|
| 1 | ✅ **Done.** `CV 4.1` was created as a copy of `CV 4.0`, submitted by the Guntur Academic Coordinator, approved and activated by the Super Admin. `CV 4.0` is Retired. Admission 8 stays on `CV 4.0` (`Allocation Pending`): activation only moves enrolments that have no version |
| 1b | ✅ **Prepared.** `CV 4.2` is created, submitted and **Approved**, but not active. Until step 3 your catalogue lists it as `status: Draft` with `lms_status: Approved`, so it can't be selected |
| 2 | **Ready for you.** Mapping admission 8 to `CV 4.1` with a reason should answer 201, `changed: true`. The next pull shows `CV 4.1` |
| 3 | **Ask the LMS side** once your worker is stopped and you have pulled. The LMS then activates `CV 4.2`, which retires `CV 4.1` |
| 4 | Y arrives and is auto-mapped to `CV 4.2`. Your mapping of Y to `CV 4.1` gets **422 `BUSINESS_RULE`**: `CV 4.1 is Retired in the LMS, so it can't be mapped. The Active version for NIT-CRS-007 is CV 4.2` |
| 5 | Your pull shows `CV 4.2` Active and `CV 4.1` Retired, with Y *Mapped* `CV 4.2` and admission 8 on `CV 4.1` |
| 6 | **Ask the LMS side** for the outage. Mapping admission 8 to `CV 4.2` while the LMS is down, then delivering it after the restart, should answer 201, `changed: true` |

**One side effect to expect.** The seed batch `NIT-VIJ-BAT-2026-000001` (also `NIT-CRS-007`) keeps teaching `CV 4.0`;
a batch keeps its own version. It is seed data, so you never see it in `batches[]`.
