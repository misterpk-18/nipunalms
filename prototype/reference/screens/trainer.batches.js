import { a as e, n as t, x as n } from "./ui-BRNtr3Vo.js";
import { l as r } from "./index-BqZ61Way.js";
import { n as i, r as a, t as o } from "./staff-zeGrIO0v.js";
var s = n(),
  c = () => {
    let n = a(),
      c = r.filter((e) => i(n, e.branch) && e.trainer !== `Unassigned`);
    return (0, s.jsx)(o, {
      title: `My assigned batches`,
      source: `LMS batch register`,
      children: (0, s.jsx)(e, {
        caption: `Assigned batches`,
        rows: c,
        getKey: (e) => e.id,
        cols: [
          { h: `Batch`, c: (e) => (0, s.jsx)(`span`, { className: `font-mono text-xs`, children: e.id }) },
          { h: `Course`, c: (e) => e.course },
          { h: `Curriculum`, c: (e) => e.curriculum },
          { h: `Students`, c: (e) => e.capacity },
          { h: `State`, c: (e) => (0, s.jsx)(t, { children: e.state }) },
        ],
      }),
    });
  };
export { c as component };
