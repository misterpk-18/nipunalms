# Nipuna LMS prototype (reference only)

Source: https://nipuna-lms-prototype.lovable.app/ (Lovable, TanStack Start, sample data, no live integrations).

`reference/` is a readable (prettier-formatted) copy of the published bundle, captured 29 Sep 2026:

| File | Contents |
|---|---|
| `reference/app-shell-routes-and-sample-data.js` | i18n strings (EN / తెలుగు), per-role navigation, app shell, route titles/descriptions, all sample data (student, enrolments, modules, topics, sessions, assignments, tests, certificates, batches, recording exceptions) |
| `reference/shared-components-and-roles.js` | Simulated roles and workspace access, status-state catalogue, shared table / tabs / grid / note components |
| `reference/screens/*.js` | One file per route (file name = route id, e.g. `trainer.reviews.js` = `/trainer/reviews`, `courses._enrolmentId.js` = `/courses/$enrolmentId`) plus shared chunks (`Readiness.js`, `Certificates.js`, `AskNipuna.js`, `staff.js`, `Notifications*.js`) |
| `reference/styles.css` | Compiled Tailwind theme (colour tokens: navy header, primary, sim) |

Use it for layout and wording only. The prototype's role switcher, "Demo" buttons and banner are UAT aids and are not
carried into the real app; behaviour comes from the approved modules and `docs/API_PLAN.md`.
