import { a as e, n as t, t as n, x as r } from "./ui-BRNtr3Vo.js";
import { b as i } from "./index-BqZ61Way.js";
import { n as a, r as o, t as s } from "./staff-zeGrIO0v.js";
var c = r(),
  l = () => {
    let r = o();
    return (0, c.jsxs)(s, {
      title: `Attendance & Progress`,
      source: `LMS progress services`,
      children: [
        (0, c.jsx)(e, {
          caption: `Progress`,
          rows: i.filter((e) => a(r, e.batch)),
          getKey: (e) => e.name,
          cols: [
            { h: `Student`, c: (e) => e.name },
            { h: `Curriculum delivered`, c: () => `46%` },
            { h: `Attendance / recovery`, c: (e) => e.attendance },
            { h: `Required learning`, c: (e) => (e.attendance === `Partial Data` ? (0, c.jsx)(t, { children: `Partial Data` }) : `62%`) },
            { h: `Engagement`, c: () => (0, c.jsx)(t, { children: `Stale` }) },
          ],
        }),
        (0, c.jsx)(n, { children: `The four measures are never merged into a single completion score.` }),
      ],
    });
  };
export { l as component };
