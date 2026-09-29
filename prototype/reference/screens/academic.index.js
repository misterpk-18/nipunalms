import { d as e, f as t, i as n, o as r, t as i, x as a } from "./ui-BRNtr3Vo.js";
import { t as o } from "./link-IIfPRlSn.js";
import { h as s, l as c } from "./index-BqZ61Way.js";
import { n as l, r as u, t as d } from "./staff-zeGrIO0v.js";
var f = a(),
  p = () => {
    let a = u(),
      p = c.filter((e) => l(a, e.branch)),
      m = s.filter((e) => l(a, e.batch));
    return (0, f.jsxs)(d, {
      title: `Academic dashboard`,
      source: `LMS academic domain`,
      children: [
        (0, f.jsxs)(r, {
          cols: 3,
          children: [
            (0, f.jsx)(e, {
              rank: 1,
              label: `Enrolments awaiting batch allocation`,
              value: a === `Vijayawada` ? 1 : 2,
              hint: `Sample · includes Curriculum Mapping Pending`,
            }),
            (0, f.jsx)(e, {
              rank: 2,
              label: `Academic results awaiting publication review`,
              value: a === `Vijayawada` ? 2 : 3,
              hint: `Sample · provisional, not published`,
            }),
            (0, f.jsx)(e, {
              rank: 3,
              label: `Unfulfilled recording promises`,
              value: m.length,
              hint: `Sample · from Recording Exception Queue`,
            }),
          ],
        }),
        (0, f.jsxs)(`div`, {
          className: `grid gap-3 sm:grid-cols-3`,
          "aria-label": `Additional academic widgets`,
          children: [
            (0, f.jsx)(e, { label: `Batches delivery-ready`, value: `${p.filter((e) => e.readiness === `Ready`).length} / ${p.length}` }),
            (0, f.jsx)(e, {
              label: `Academic reviews awaiting`,
              value: a === `Vijayawada` ? 2 : 5,
              hint: `Content, assessments, completion`,
            }),
            (0, f.jsx)(e, { label: `Open exceptions`, value: m.length + 1, hint: `Recording + curriculum mapping` }),
          ],
        }),
        p.some((e) => e.curriculum === `Curriculum Mapping Pending`) &&
          (0, f.jsx)(t, {
            state: `Pending Verification`,
            children: `NIT-GNT-BAT-2026-000003: Curriculum Mapping Pending · Recovery Owner: Academic Coordinator — Guntur. Paid receipts and Admissions are preserved.`,
          }),
        (0, f.jsx)(n, {
          title: `Quick links`,
          children: (0, f.jsx)(`div`, {
            className: `flex flex-wrap gap-2 text-sm`,
            children: [
              [`/academic/curriculum`, `Curriculum versions`],
              [`/academic/batches`, `Batch management`],
              [`/academic/schedule`, `Schedule`],
              [`/academic/recording-exceptions`, `Recording exceptions`],
              [`/academic/completion`, `Completion review`],
              [`/academic/certificates`, `Certificate eligibility`],
            ].map(([e, t]) =>
              (0, f.jsx)(o, { to: e, className: `tap inline-flex items-center rounded-lg border px-3 hover:bg-accent`, children: t }, e),
            ),
          }),
        }),
        (0, f.jsx)(i, {
          children: `Four distinct records: Accepted Delivery Plan · Batch · Course Enrolment / component allocation · Actual Class Session.`,
        }),
      ],
    });
  };
export { p as component };
