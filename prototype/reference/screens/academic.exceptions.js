import { a as e, n as t, u as n, x as r } from "./ui-BRNtr3Vo.js";
import { t as i } from "./staff-zeGrIO0v.js";
var a = r(),
  o = [
    {
      id: `EX-201`,
      kind: `Curriculum Mapping Pending`,
      ref: `NIT-CRS-052 · Sample Student`,
      owner: `Academic Coordinator — Guntur`,
      s: `Open`,
    },
    { id: `EX-202`, kind: `Attendance recovery`, ref: `ses-101 · REC-0041`, owner: `Academic Coordinator — Guntur`, s: `Approved` },
    {
      id: `EX-203`,
      kind: `Transfer in progress`,
      ref: `Sample Learner K · GNT → VIJ`,
      owner: `Academic Coordinator — Vijayawada`,
      s: `Pending Verification`,
    },
    {
      id: `EX-204`,
      kind: `Recording access after 2nd anniversary`,
      ref: `Sample Learner L`,
      owner: `Founder/CEO or Super Admin exception`,
      s: `Awaiting Approval`,
    },
  ],
  s = () =>
    (0, a.jsx)(i, {
      title: `Exception / Recovery queue`,
      children: (0, a.jsx)(e, {
        caption: `Exceptions`,
        rows: o,
        getKey: (e) => e.id,
        cols: [
          { h: `ID`, c: (e) => e.id },
          { h: `Type`, c: (e) => e.kind },
          { h: `Reference`, c: (e) => e.ref },
          { h: `Recovery owner`, c: (e) => e.owner },
          { h: `State`, c: (e) => (0, a.jsx)(t, { children: e.s }) },
          { h: `Action`, c: () => (0, a.jsx)(n, { variant: `outline`, message: `Recovery step logged.`, children: `Update` }) },
        ],
      }),
    });
export { s as component };
