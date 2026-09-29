import { a as e, n as t, u as n, x as r } from "./ui-BRNtr3Vo.js";
import { t as i } from "./staff-zeGrIO0v.js";
var a = r(),
  o = [
    { id: `1`, who: `Sample Learner C (GNT)`, course: `NIT-CRS-019`, del: `100%`, att: `92%`, req: `100%`, s: `Eligibility Review` },
    {
      id: `2`,
      who: `Sample Learner D (VIJ)`,
      course: `NIT-CRS-007`,
      del: `100%`,
      att: `88%`,
      req: `95% — 1 required item missing`,
      s: `Awaiting Approval`,
    },
    { id: `3`, who: `Sample Student — Anvitha K.`, course: `NIT-CRS-018`, del: `46%`, att: `86%`, req: `62%`, s: `Not Yet Eligible` },
  ],
  s = () =>
    (0, a.jsx)(i, {
      title: `Completion Review`,
      children: (0, a.jsx)(e, {
        caption: `Completion review`,
        rows: o,
        getKey: (e) => e.id,
        cols: [
          { h: `Student`, c: (e) => e.who },
          { h: `Course`, c: (e) => e.course },
          { h: `Delivered`, c: (e) => e.del },
          { h: `Attendance`, c: (e) => e.att },
          { h: `Required learning`, c: (e) => e.req },
          { h: `State`, c: (e) => (0, a.jsx)(t, { children: e.s }) },
          {
            h: `Action`,
            c: () => (0, a.jsx)(n, { variant: `outline`, message: `Completion recommendation sent for approval.`, children: `Recommend` }),
          },
        ],
      }),
    });
export { s as component };
