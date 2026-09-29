import { a as e, n as t, t as n, x as r } from "./ui-BRNtr3Vo.js";
import { g as i, p as a } from "./index-BqZ61Way.js";
import { r as o, t as s } from "./staff-zeGrIO0v.js";
var c = r(),
  l = () => {
    let r = o();
    return (0, c.jsxs)(s, {
      title: `Schedule / Actual Class Sessions`,
      source: `LMS schedule`,
      children: [
        (0, c.jsx)(e, {
          caption: `Sessions`,
          rows: i.filter((e) => !r || e.branch === r),
          getKey: (e) => e.id,
          cols: [
            { h: `When (IST)`, c: (e) => `${e.date} · ${e.time}` },
            { h: `Session`, c: (e) => e.title },
            { h: `Batch`, c: (e) => (0, c.jsx)(`span`, { className: `font-mono text-xs`, children: e.batch }) },
            { h: `Trainer`, c: (e) => e.trainer },
            {
              h: `Meet association`,
              c: (e) => (0, c.jsxs)(`span`, { className: `text-xs`, children: [a[e.branch], ` · Pending Verification`] }),
            },
            { h: `State`, c: (e) => (0, c.jsx)(t, { children: e.state }) },
          ],
        }),
        (0, c.jsx)(n, {
          children: `LMS manages scheduled class, Calendar/Meet association, actual Class Session and attendance evidence. No Google connection exists in this prototype.`,
        }),
      ],
    });
  };
export { l as component };
