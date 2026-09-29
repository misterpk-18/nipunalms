import { a as e, n as t, t as n, u as r, x as i } from "./ui-BRNtr3Vo.js";
import { t as a } from "./staff-zeGrIO0v.js";
var o = i(),
  s = [
    { id: `EXT-031`, kind: `Recording/material extension to 2nd anniversary`, who: `Sample Student — Anvitha K.`, s: `Pending review` },
    { id: `EXT-032`, kind: `Extension after first expiry (remaining time to 2nd anniversary)`, who: `Sample Learner M.`, s: `Approved` },
    { id: `EXT-033`, kind: `Request after 2nd anniversary`, who: `Sample Learner L.`, s: `Needs Founder/CEO or Super Admin exception` },
    { id: `ESC-014`, kind: `Trainer absence escalation`, who: `NIT-GNT-BAT-2026-000002`, s: `Open` },
  ],
  c = () =>
    (0, o.jsxs)(a, {
      title: `Escalations & access-extension requests`,
      children: [
        (0, o.jsx)(e, {
          caption: `Requests`,
          rows: s,
          getKey: (e) => e.id,
          cols: [
            { h: `ID`, c: (e) => e.id },
            { h: `Type`, c: (e) => e.kind },
            { h: `Subject`, c: (e) => e.who },
            { h: `State`, c: (e) => (0, o.jsx)(t, { children: e.s }) },
            { h: `Action`, c: () => (0, o.jsx)(r, { variant: `outline`, message: `Decision recorded locally.`, children: `Decide` }) },
          ],
        }),
        (0, o.jsx)(n, { children: `Repeated extension requests do not stack years.` }),
      ],
    });
export { c as component };
