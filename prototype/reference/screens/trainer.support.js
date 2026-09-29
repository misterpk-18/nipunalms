import { a as e, n as t, u as n, x as r } from "./ui-BRNtr3Vo.js";
import { b as i } from "./index-BqZ61Way.js";
import { n as a, r as o, t as s } from "./staff-zeGrIO0v.js";
var c = r(),
  l = () => {
    let r = o();
    return (0, c.jsx)(s, {
      title: `Student support flags`,
      children: (0, c.jsx)(e, {
        caption: `Support flags`,
        rows: i.filter((e) => e.flag !== `None` && a(r, e.batch)),
        getKey: (e) => e.name,
        cols: [
          { h: `Student`, c: (e) => e.name },
          { h: `Flag`, c: (e) => (0, c.jsx)(t, { children: e.flag }) },
          {
            h: `Action`,
            c: () => (0, c.jsx)(n, { variant: `outline`, message: `Escalated to Academic Coordinator (prototype).`, children: `Escalate` }),
          },
        ],
      }),
    });
  };
export { l as component };
