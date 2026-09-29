import { f as e, i as t, l as n, o as r, x as i } from "./ui-BRNtr3Vo.js";
import { t as a } from "./staff-zeGrIO0v.js";
var o = i(),
  s = () =>
    (0, o.jsx)(a, {
      title: `Reports`,
      source: `LMS reporting (sample)`,
      children: (0, o.jsxs)(r, {
        cols: 2,
        children: [
          (0, o.jsx)(t, { title: `Curriculum delivered`, children: (0, o.jsx)(n, { value: 46, label: `NIT-GNT-BAT-2026-000001` }) }),
          (0, o.jsx)(t, { title: `Attendance (trainer-confirmed)`, children: (0, o.jsx)(n, { value: 84, label: `Batch average` }) }),
          (0, o.jsx)(t, {
            title: `Review turnaround`,
            children: (0, o.jsx)(e, { state: `Partial Data`, children: `2 submissions missing timestamps.` }),
          }),
          (0, o.jsx)(t, { title: `Engagement`, children: (0, o.jsx)(e, { state: `Stale` }) }),
        ],
      }),
    });
export { s as component };
