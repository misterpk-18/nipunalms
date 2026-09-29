import { a as e, i as t, n, u as r, x as i } from "./ui-BRNtr3Vo.js";
import { l as a } from "./index-BqZ61Way.js";
import { n as o, r as s, t as c } from "./staff-zeGrIO0v.js";
var l = i(),
  u = [
    [`Service branch`, `Guntur ✓`],
    [`Course`, `NIT-CRS-052 ✓`],
    [`Curriculum mapping / version`, `✗ Curriculum Mapping Pending`],
    [`Capacity`, `3 / 25 ✓`],
    [`Enrolment state`, `Admission verified (CRM) ✓`],
    [`Transfer state`, `None ✓`],
  ],
  d = () => {
    let i = s();
    return (0, l.jsxs)(c, {
      title: `Batch Management`,
      source: `LMS batch register`,
      children: [
        (0, l.jsx)(e, {
          caption: `Batches`,
          rows: a.filter((e) => o(i, e.branch)),
          getKey: (e) => e.id,
          cols: [
            { h: `Batch ID`, c: (e) => (0, l.jsx)(`span`, { className: `font-mono text-xs`, children: e.id }) },
            { h: `Course`, c: (e) => e.course },
            { h: `Curriculum`, c: (e) => e.curriculum },
            { h: `Capacity`, c: (e) => e.capacity },
            { h: `Trainer`, c: (e) => e.trainer },
            { h: `Readiness`, c: (e) => (0, l.jsx)(n, { children: e.readiness }) },
          ],
        }),
        (0, l.jsxs)(t, {
          title: `Batch allocation review — Sample Student (NIT-CRS-052 complimentary)`,
          children: [
            (0, l.jsx)(`ul`, {
              className: `grid gap-2 sm:grid-cols-2`,
              children: u.map(([e, t]) =>
                (0, l.jsxs)(
                  `li`,
                  {
                    className: `rounded-lg border p-2 text-sm`,
                    children: [
                      (0, l.jsxs)(`span`, { className: `text-muted-foreground`, children: [e, `: `] }),
                      (0, l.jsx)(`strong`, { children: t }),
                    ],
                  },
                  e,
                ),
              ),
            }),
            (0, l.jsxs)(`p`, {
              className: `mt-3 text-sm`,
              children: [
                `Result: `,
                (0, l.jsx)(n, { children: `Curriculum Mapping Pending` }),
                ` · Recovery Owner: Academic Coordinator — Guntur. Paid receipt and Admission preserved.`,
              ],
            }),
            (0, l.jsx)(`p`, {
              className: `mt-2 text-xs text-muted-foreground`,
              children: `Milestones stay separate: Accepted delivery plan → Admission (plan + qualifying verified first payment) → Batch allocation → Joining Date (first confirmed regular class; demo excluded).`,
            }),
            (0, l.jsxs)(`div`, {
              className: `mt-3 flex flex-wrap gap-2`,
              children: [
                (0, l.jsx)(r, { message: `Allocation held until curriculum mapping is completed.`, children: `Hold allocation` }),
                (0, l.jsx)(r, { variant: `outline`, message: `Trainer assignment change (prototype).`, children: `Assign trainer` }),
              ],
            }),
          ],
        }),
      ],
    });
  };
export { d as component };
