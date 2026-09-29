import { a as e, n as t, t as n, x as r } from "./ui-BRNtr3Vo.js";
import { b as i } from "./index-BqZ61Way.js";
import { n as a, r as o, t as s } from "./staff-zeGrIO0v.js";
var c = r(),
  l = () => {
    let r = o();
    return (0, c.jsxs)(s, {
      title: `Assigned students`,
      source: `LMS enrolments (assigned batches only)`,
      children: [
        (0, c.jsx)(e, {
          caption: `Students`,
          rows: i.filter((e) => a(r, e.batch)),
          getKey: (e) => e.name,
          cols: [
            { h: `Student`, c: (e) => e.name },
            { h: `Batch`, c: (e) => (0, c.jsx)(`span`, { className: `font-mono text-xs`, children: e.batch }) },
            { h: `Attendance`, c: (e) => e.attendance },
            { h: `Support flag`, c: (e) => (0, c.jsx)(t, { children: e.flag }) },
          ],
        }),
        (0, c.jsx)(n, { children: `Contact details and finance are not visible to trainers.` }),
      ],
    });
  };
export { l as component };
