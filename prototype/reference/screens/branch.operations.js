import { a as e, n as t, x as n } from "./ui-BRNtr3Vo.js";
import { b as r, g as i, l as a } from "./index-BqZ61Way.js";
import { n as o, r as s, t as c } from "./staff-zeGrIO0v.js";
var l = n(),
  u = () => {
    let n = s();
    return (0, l.jsxs)(c, {
      title: `Batches, schedule & people`,
      children: [
        (0, l.jsx)(`h2`, { className: `font-semibold`, children: `Batches` }),
        (0, l.jsx)(e, {
          caption: `Batches`,
          rows: a.filter((e) => o(n, e.branch)),
          getKey: (e) => e.id,
          cols: [
            { h: `Batch`, c: (e) => (0, l.jsx)(`span`, { className: `font-mono text-xs`, children: e.id }) },
            { h: `Course`, c: (e) => e.course },
            { h: `Trainer`, c: (e) => e.trainer },
            { h: `Readiness`, c: (e) => (0, l.jsx)(t, { children: e.readiness }) },
          ],
        }),
        (0, l.jsx)(`h2`, { className: `font-semibold`, children: `Upcoming sessions` }),
        (0, l.jsx)(e, {
          caption: `Sessions`,
          rows: i.filter((e) => (!n || e.branch === n) && e.state === `Scheduled`),
          getKey: (e) => e.id,
          cols: [
            { h: `When`, c: (e) => `${e.date} · ${e.time}` },
            { h: `Session`, c: (e) => e.title },
            { h: `Trainer`, c: (e) => e.trainer },
          ],
        }),
        (0, l.jsx)(`h2`, { className: `font-semibold`, children: `Students with flags` }),
        (0, l.jsx)(e, {
          caption: `Students`,
          rows: r.filter((e) => o(n, e.batch)),
          getKey: (e) => e.name,
          cols: [
            { h: `Student`, c: (e) => e.name },
            { h: `Attendance`, c: (e) => e.attendance },
            { h: `Flag`, c: (e) => (0, l.jsx)(t, { children: e.flag }) },
          ],
        }),
      ],
    });
  };
export { u as component };
