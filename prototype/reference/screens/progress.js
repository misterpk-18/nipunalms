import { c as e, f as t, i as n, l as r, t as i, x as a } from "./ui-BRNtr3Vo.js";
import { x as o } from "./index-BqZ61Way.js";
var s = a();
function c() {
  let a = o();
  return (0, s.jsxs)(`div`, {
    className: `mx-auto max-w-5xl`,
    children: [
      (0, s.jsx)(e, { title: a(`progress`), subtitle: `NIT-CRS-018 · Four measures, never merged`, source: `LMS progress services` }),
      (0, s.jsxs)(`div`, {
        className: `grid gap-4 md:grid-cols-2`,
        children: [
          (0, s.jsxs)(n, {
            title: `1 · Curriculum Delivered`,
            children: [
              (0, s.jsx)(r, { value: 46, label: `Topics delivered by trainers` }),
              (0, s.jsx)(`p`, { className: `mt-2 text-xs text-muted-foreground`, children: `What has been taught to your batch.` }),
            ],
          }),
          (0, s.jsxs)(n, {
            title: `2 · Attendance / Approved Recovery`,
            children: [
              (0, s.jsx)(r, { value: 86, label: `Present + approved recovery` }),
              (0, s.jsx)(`p`, { className: `mt-2 text-xs text-muted-foreground`, children: `1 approved recovery included (REC-0041).` }),
            ],
          }),
          (0, s.jsx)(n, {
            title: `3 · Required Learning Completed`,
            children: (0, s.jsx)(r, { value: 62, label: `Required assignments/tests completed` }),
          }),
          (0, s.jsx)(n, {
            title: `4 · LMS Engagement`,
            children: (0, s.jsx)(t, { state: `Stale`, children: `Last refreshed 6 h ago. Engagement is informational only.` }),
          }),
        ],
      }),
      (0, s.jsx)(`div`, {
        className: `mt-4`,
        children: (0, s.jsx)(i, {
          children: `Course completion and certificate eligibility are decided through Completion Review — not from any single percentage.`,
        }),
      }),
    ],
  });
}
export { c as component };
