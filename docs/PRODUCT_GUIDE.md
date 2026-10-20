# Nipuna LMS — Product guide

How the product works, as flowcharts. Each chart has a line or two of explanation; the details live in the other docs
(see [Where to go next](#13-where-to-go-next)). The charts are [Mermaid](https://mermaid.js.org/) and draw on GitHub and in
VS Code's Markdown preview.

**Contents:** [1 Big picture](#1-the-big-picture) · [2 Roles](#2-who-uses-it) · [3 Admission to first class](#3-from-admission-to-first-class) ·
[4 Enrolment status](#4-the-life-of-an-enrolment) · [5 Batches](#5-setting-up-a-batch) · [6 Class day](#6-a-class-day) ·
[7 Attendance](#7-attendance) · [8 Content and access](#8-content-recordings-and-how-long-a-student-can-use-them) ·
[9 Work and tests](#9-assignments-and-tests) · [10 Results](#10-results) · [11 Certificates](#11-completion-and-certificates) ·
[12 Who decides](#12-who-decides-what) · [13 Next](#13-where-to-go-next)

---

## 1. The big picture

The CRM owns admissions and money. The LMS owns learning. The CRM tells the LMS about each admission; the LMS tells the CRM
how the student is doing.

```mermaid
flowchart LR
    CRM["CRM - admissions and fees"]
    LMS["LMS - learning"]
    STU["Student"]
    STAFF["Trainers and managers"]

    CRM -->|"admission, course and finance events"| LMS
    LMS -->|"login id, batch, progress, certificates"| CRM
    LMS --> STU
    LMS --> STAFF
    STU -->|"attends, submits work, takes tests"| LMS
    STAFF -->|"teach, mark, review, approve"| LMS
```

The LMS never edits money. It only shows a read-only summary of what the CRM sends.

---

## 2. Who uses it

Each login has exactly one role. A Branch Manager sees only the branch chosen at sign-in.

```mermaid
flowchart TB
    subgraph learners["Learners"]
        S["Student - own course, classes, work, results"]
    end
    subgraph branch["One branch"]
        T["Trainer - their batches, classes, grading"]
        BM["Branch Manager - batches, allocation, attendance, approvals"]
    end
    subgraph company["All branches"]
        SA["Super Admin - setup, accounts, courses, allocation"]
        F["Founder / CEO - all the Super Admin does, plus the Founder's inbox"]
    end

    BM -->|"manages"| T
    BM -->|"serves"| S
    T -->|"teaches"| S
    SA -->|"reads and decides across all branches"| BM
    F -->|"final say on exceptions"| BM
```

---

## 3. From admission to first class

What happens between a counsellor saving an admission in the CRM and the student sitting in a first class.

```mermaid
flowchart TD
    A["CRM sends AdmissionQualified"] --> B{"Event seen before, or an older version?"}
    B -->|"yes"| B1["Ignored, nothing changes"]
    B -->|"no"| C["Student record created or reused, one login per person"]
    C --> D["Admission and enrolment created"]
    D --> E{"Complimentary course gate met?"}
    E -->|"no"| E1["Provisioning Pending"]
    E -->|"yes"| F["Allocation Pending"]
    C --> G["Activation link made for a new login"]
    G --> H["Student sets their own password"]
    F --> I["Appears on Waiting for a batch - Branch Manager is told"]
    I --> J["Branch Manager allocates a batch"]
    J --> K["Allocated, awaiting first regular class"]
    K --> L["First class held, student marked Present or Late"]
    L --> M["Joining Date set, enrolment Active"]
```

Two things worth knowing: a student signs in with their Student ID (or email), never a mobile number, and the Joining Date
is the day of the first attended class, not the day of allocation.

---

## 4. The life of an enrolment

```mermaid
flowchart TD
    P["Provisioning Pending"] --> AP["Allocation Pending"]
    AP -->|"batch seat given"| AW["Allocated, awaiting first regular class"]
    AW -->|"first Present or Late"| AC["Active"]
    AW -->|"seat taken away"| AP
    AC --> PA["Paused"]
    PA --> AC
    AC -->|"completion decided Complete"| CO["Completed"]
    AP --> WD["Withdrawn"]
    AW --> WD
    AC --> WD
```

Paused and Withdrawn come from the CRM pausing or cancelling the admission. A completed or withdrawn enrolment keeps its batch history.

---

## 5. Setting up a batch

A batch is a group of students learning one course at one branch on one timetable.

```mermaid
flowchart TD
    A["Create batch - course, mode, days, times, capacity"] --> B["Add trainers and room"]
    B --> C{"Readiness checks pass?"}
    C -->|"no"| B
    C -->|"yes"| D["Propose and confirm, one step for a Branch Manager"]
    D --> E["Starting"]
    E --> F["Create classes from the timetable, with a preview"]
    F --> G["Running"]
    G --> H["Full, derived from capacity"]
    H --> G
    G --> I["Completed"]
    A -.-> X["Cancelled, only while no seat is held"]
    E -.-> Y["On Hold"]
    G -.-> Y
    Y -.-> E
    I --> Z["Archived"]
```

A warning on confirmation needs a written override reason and is audited. After confirmation, changes to start date,
mode or timetable are *material changes*: each student is asked to agree before the change applies.

```mermaid
flowchart TD
    M1["Manager asks for a material change"] --> M2["An independent reviewer decides"]
    M2 -->|"approved"| M3["Each student is asked to agree"]
    M3 --> M4{"Everyone agreed, or declined with an alternative?"}
    M4 -->|"yes"| M5["Change applied"]
    M4 -->|"no"| M3
    M2 -->|"rejected"| M6["Nothing changes"]
```

---

## 6. A class day

Every class moves Scheduled → Live → Delivered. The trainer runs it from one guided screen.

```mermaid
flowchart TD
    A["Class scheduled: room, or Meet link for online"] --> B{"Link ready?"}
    B -->|"no"| B1["Trainer taps No Meet link, Branch Managers are alerted"]
    B1 --> B2["Manager records the link"]
    B2 --> C
    B -->|"yes"| C["Trainer starts the class"]
    C --> D["Class is Live"]
    D --> E["Trainer joins and teaches"]
    E --> F["Marks attendance"]
    F --> G["Writes the class log"]
    G --> H["Class is Delivered"]
    D -->|"late or disrupted"| I["Students told, disruption recorded, recovery plan agreed"]
    I --> E
```

When a class does not happen:

```mermaid
flowchart TD
    A["Class cannot go ahead"] --> B{"Who asks?"}
    B -->|"trainer"| C["Reschedule request"]
    B -->|"manager"| D["Cancel or reschedule directly, with a reason"]
    C --> E["Branch Manager decides"]
    E -->|"approved"| F["Class moved, everyone told"]
    E -->|"rejected"| G["Trainer told, class stays"]
    D --> F
    D --> H["A cancelled regular class owes a replacement until one is held or waived"]
```

---

## 7. Attendance

An unmarked seat shows as *Not yet marked*, never as a guessed absence.

```mermaid
flowchart TD
    A["Class Live or Delivered"] --> B["Trainer marks the register: all Present, then the exceptions"]
    B --> C{"Within 7 days of the class?"}
    C -->|"yes"| D["Can be re-marked"]
    C -->|"no"| E["Locked"]
    E --> F["Request a correction with a reason"]
    F --> G["A different Branch Manager decides - Founder if the requester is a manager"]
    G -->|"approved"| H["Entry changed, old value kept in the audit log"]
    G -->|"rejected"| I["Entry stays"]
    B -->|"student marked Absent"| J["Student is told"]
    J --> K["Student or trainer asks for recovery"]
    K --> L["Branch Manager approves or rejects"]
    L -->|"approved"| M["Recovery done: recording watched, extra session or assignment"]
    M --> N["Trainer verifies, recovery Completed"]
```

The attendance percentage counts Present and Late over the classes marked while the student held a seat. A recovery is
reported separately.

For an online class the student can also say **I attended** on the class page once it has started. That is not attendance: the
trainer's register is the only record. The register shows "Says they attended" beside those students, and the trainer can mark
them all Present in one step or mark each one themselves.

---

## 8. Content, recordings and how long a student can use them

```mermaid
flowchart TD
    A["Trainer uploads a file or link"] --> B["Submitted"]
    B --> C["Branch Manager reviews"]
    C -->|"approved"| D["Released to the batch"]
    C -->|"changes requested"| A
    C -->|"rejected"| X["Not shown"]
    E["Class recording ready"] --> F["Branch Manager releases it"]
    F --> G["Students see it in My Learning"]
```

Access to recordings and materials runs from the Joining Date.

```mermaid
flowchart TD
    J["Joining Date set"] --> A["Access for 1 year"]
    A --> B{"Student asks for more time"}
    B --> C["Branch Manager approves one extra year, ending on the 2nd anniversary"]
    C --> D["Access to 2 years, no further stacking"]
    D --> E{"Asks after the 2nd anniversary?"}
    E -->|"yes"| F["Branch Manager adds a recommendation"]
    F --> G["Founder or Super Admin decides and states the new expiry"]
```

---

## 9. Assignments and tests

**Assignments**

```mermaid
flowchart TD
    A1["Trainer creates and releases"] --> A2["Student submits a file up to 10 MB"]
    A2 --> A3["Trainer starts review"]
    A3 --> A4{"Outcome"}
    A4 -->|"Reviewed with marks"| A5["Provisional result"]
    A4 -->|"Resubmission requested"| A2
```

**Tests**

```mermaid
flowchart TD
    T1["Trainer builds the test from approved questions"] --> T2{"Formal test?"}
    T2 -->|"yes"| T3["Branch Manager approves"]
    T2 -->|"no"| T4["Released"]
    T3 --> T4
    T4 --> T5["Student starts an attempt with timer and autosave"]
    T5 --> T6["Submit, or auto-submit at the deadline"]
    T6 --> T7{"Needs hand grading?"}
    T7 -->|"yes"| T8["Trainer grades"]
    T7 -->|"no"| T9["Scored at once"]
    T8 --> T10["Provisional result"]
```

Test questions are written by trainers and approved by a Branch Manager who did not write them. Approved questions are frozen;
a change makes a new version.

---

## 10. Results

A student sees marks and feedback only once a result is published.

```mermaid
flowchart LR
    A["Provisional: trainer's marks"] --> B["Moderated: Branch Manager adjusts with a reason"]
    B --> C["Published"]
    A --> C
    C --> D["Student is told and sees the score"]
```

Practice quizzes and mock tests are scored at once and make no result.

---

## 11. Completion and certificates

```mermaid
flowchart TD
    A["Student has been learning"] --> B["Completion review opened"]
    B --> C["Trainer recommends"]
    C --> D{"Branch Manager decides"}
    D -->|"Not Yet"| A
    D -->|"Needs Recovery"| R["Recovery work"]
    R --> A
    D -->|"Complete"| E["Enrolment Completed, certificate enters Eligibility Review"]
    E --> F{"Fee cleared?"}
    F -->|"no"| G["Financial exception asked - Founder or Super Admin decides"]
    G --> H
    F -->|"yes"| H["Awaiting Approval"]
    H --> I["Branch Manager approves"]
    I --> J["Issued: number NIT-CERT-year-number, PDF with QR code"]
    J --> K["Anyone can verify the number online"]
```

After issue, a certificate can be changed only through a request:

```mermaid
flowchart LR
    A["Issued"] -->|"correction"| B["New version, same number; earlier version Superseded"]
    A -->|"revocation"| C["Revoked - Founder or Super Admin decides"]
    C -->|"reinstatement"| A
```

Each issued, superseded or revoked version is sent back to the CRM.

---

## 12. Who decides what

The rule behind most approvals: **the person who asked never decides their own request.**

```mermaid
flowchart TD
    A["Someone asks for a correction, change or request"] --> B{"Who asked?"}
    B -->|"student, trainer or other staff"| C["A Branch Manager decides"]
    B -->|"a Branch Manager"| D["Founder or Super Admin decides"]
    C --> E{"Routine?"}
    E -->|"yes"| F["Decided alone"]
    E -->|"an exception beyond the branch's limit"| D
    D --> G["Decision, reason and old and new values written to the audit log"]
    F --> G
```

Sensitive decisions (approving or issuing a certificate, deciding corrections) ask the person to sign in again first.

---

## 13. Where to go next

| You want | Open |
|---|---|
| Set the project up and run it | [DEVELOPMENT.md](DEVELOPMENT.md) |
| Every endpoint, role rule and status | [API.md](API.md) |
| The tables, migrations and what the database enforces | [DATABASE.md](DATABASE.md) |
| The CRM contract and its events | [CRM_INTEGRATION.md](CRM_INTEGRATION.md) |
