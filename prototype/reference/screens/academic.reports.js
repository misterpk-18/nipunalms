import { f as e, i as t, l as n, o as r, x as i } from "./ui-BRNtr3Vo.js";
import { t as a } from "./staff-zeGrIO0v.js";
var o = i(),
  s = () =>
    (0, o.jsx)(a, {
      title: `Academic Reports`,
      source: `LMS reporting (sample)`,
      children: (0, o.jsxs)(r, {
        cols: 2,
        children: [
          (0, o.jsx)(t, { title: `Curriculum delivered (branch)`, children: (0, o.jsx)(n, { value: 58, label: `All running batches` }) }),
          (0, o.jsx)(t, { title: `Attendance / approved recovery`, children: (0, o.jsx)(n, { value: 84, label: `Branch average` }) }),
          (0, o.jsx)(t, {
            title: `Completion reviews closed`,
            children: (0, o.jsx)(e, { state: `Partial Data`, children: `VIJ data incomplete for Sep.` }),
          }),
          (0, o.jsx)(t, {
            title: `Certificate issue lead time`,
            children: (0, o.jsx)(e, { state: `Integration Unavailable`, children: `Not Configured.` }),
          }),
        ],
      }),
    });
export { s as component };
