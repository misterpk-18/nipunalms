import { a as e, n as t, u as n, x as r } from "./ui-BRNtr3Vo.js";
import { t as i } from "./staff-zeGrIO0v.js";
var a = r(),
  o = [
    { id: `a1`, item: `Supervised Learning module test`, kind: `Module test`, batch: `NIT-GNT-BAT-2026-000001`, s: `Awaiting moderation` },
    { id: `a2`, item: `SQL coding exercise results`, kind: `Coding`, batch: `NIT-GNT-BAT-2026-000001`, s: `Provisional — publish pending` },
    { id: `a3`, item: `Regression assignment rubric`, kind: `Assignment`, batch: `NIT-GNT-BAT-2026-000001`, s: `Approved` },
    { id: `a4`, item: `AWS final test paper`, kind: `Final test`, batch: `NIT-VIJ-BAT-2026-000001`, s: `Configuration Pending` },
  ],
  s = () =>
    (0, a.jsx)(i, {
      title: `Assignment / Assessment Review`,
      children: (0, a.jsx)(e, {
        caption: `Assessment reviews`,
        rows: o,
        getKey: (e) => e.id,
        cols: [
          { h: `Item`, c: (e) => e.item },
          { h: `Type`, c: (e) => (0, a.jsx)(t, { tone: `info`, children: e.kind }) },
          { h: `Batch`, c: (e) => (0, a.jsx)(`span`, { className: `font-mono text-xs`, children: e.batch }) },
          { h: `State`, c: (e) => (0, a.jsx)(t, { children: e.s }) },
          {
            h: `Action`,
            c: () => (0, a.jsx)(n, { variant: `outline`, message: `Results would be published to students.`, children: `Publish` }),
          },
        ],
      }),
    });
export { s as component };
