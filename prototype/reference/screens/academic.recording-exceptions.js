import { a as e, f as t, n, u as r, x as i } from "./ui-BRNtr3Vo.js";
import { h as a } from "./index-BqZ61Way.js";
import { n as o, r as s, t as c } from "./staff-zeGrIO0v.js";
var l = i(),
  u = () => {
    let i = s();
    return (0, l.jsxs)(c, {
      title: `Recording Exception Queue`,
      source: `LMS recording mapping (simulated)`,
      children: [
        (0, l.jsx)(t, { state: `Integration Unavailable`, children: `No Drive or Meet connection — exceptions are sample records.` }),
        (0, l.jsx)(e, {
          caption: `Recording exceptions`,
          rows: a.filter((e) => o(i, e.batch)),
          getKey: (e) => e.id,
          cols: [
            { h: `ID`, c: (e) => e.id },
            { h: `Session`, c: (e) => e.session },
            { h: `Batch`, c: (e) => (0, l.jsx)(`span`, { className: `font-mono text-xs`, children: e.batch }) },
            { h: `Issue`, c: (e) => e.issue },
            { h: `Status`, c: (e) => (0, l.jsx)(n, { children: e.status }) },
            { h: `Owner`, c: (e) => e.owner },
            { h: `Action`, c: () => (0, l.jsx)(r, { variant: `outline`, message: `Exception resolution logged.`, children: `Resolve` }) },
          ],
        }),
      ],
    });
  };
export { u as component };
