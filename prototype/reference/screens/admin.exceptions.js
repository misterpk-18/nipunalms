import { a as e, n as t, x as n } from "./ui-BRNtr3Vo.js";
import { h as r } from "./index-BqZ61Way.js";
import { t as i } from "./staff-zeGrIO0v.js";
var a = n(),
  o = [
    ...r.map((e) => ({ id: e.id, queue: `Meet / recording`, item: `${e.batch} · ${e.issue}`, owner: e.owner, s: e.status })),
    {
      id: `AC-07`,
      queue: `Access / recovery`,
      item: `Sample Learner L — access after 2nd anniversary`,
      owner: `Super Admin`,
      s: `Awaiting Approval`,
    },
    {
      id: `AC-08`,
      queue: `Access / recovery`,
      item: `Emergency elevated access (4 h max) — sample`,
      owner: `Super Admin`,
      s: `Configuration Pending`,
    },
    { id: `SY-03`, queue: `CRM/LMS sync`, item: `Receipt.verified not received`, owner: `Super Admin`, s: `Integration Unavailable` },
    { id: `PV-12`, queue: `Provisioning`, item: `Meet association NIT-VIJ-BAT-2026-000001`, owner: `Super Admin`, s: `Failed` },
  ],
  s = () =>
    (0, a.jsx)(i, {
      title: `Exception Queues — all branches`,
      children: (0, a.jsx)(e, {
        caption: `Exceptions`,
        rows: o,
        getKey: (e) => e.id,
        cols: [
          { h: `ID`, c: (e) => e.id },
          { h: `Queue`, c: (e) => e.queue },
          { h: `Item`, c: (e) => e.item },
          { h: `Owner`, c: (e) => e.owner },
          { h: `State`, c: (e) => (0, a.jsx)(t, { children: e.s }) },
        ],
      }),
    });
export { s as component };
