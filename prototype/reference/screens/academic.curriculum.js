import { a as e, n as t, t as n, x as r } from "./ui-BRNtr3Vo.js";
import { d as i } from "./index-BqZ61Way.js";
import { t as a } from "./staff-zeGrIO0v.js";
var o = r(),
  s = [
    { code: i[0].code, name: i[0].name, v: `Parent Programme v2026.1 (3 tracks + booster)`, state: `Active`, ready: `Ready` },
    { code: i[1].code, name: i[1].name, v: `CV 5.1`, state: `Active`, ready: `Ready` },
    { code: i[2].code, name: i[2].name, v: `CV 3.0 draft`, state: `In review`, ready: `Curriculum Mapping Pending` },
    { code: i[3].code, name: i[3].name, v: `CV 4.0`, state: `Active`, ready: `Ready` },
    { code: i[4].code, name: i[4].name, v: `Booster CV 1.3`, state: `Active`, ready: `Ready` },
  ],
  c = () =>
    (0, o.jsxs)(a, {
      title: `Course Curriculum & Versions`,
      source: `LMS curriculum register`,
      children: [
        (0, o.jsx)(e, {
          caption: `Curriculum versions`,
          rows: s,
          getKey: (e) => e.code,
          cols: [
            {
              h: `Course`,
              c: (e) =>
                (0, o.jsxs)(o.Fragment, {
                  children: [
                    (0, o.jsx)(`span`, { className: `font-mono text-xs`, children: e.code }),
                    (0, o.jsx)(`div`, { children: e.name }),
                  ],
                }),
            },
            { h: `Version`, c: (e) => e.v },
            { h: `State`, c: (e) => (0, o.jsx)(t, { children: e.state }) },
            { h: `Delivery readiness`, c: (e) => (0, o.jsx)(t, { children: e.ready }) },
          ],
        }),
        (0, o.jsx)(n, {
          children: `Course Master names/codes are read-only here; global Course Master administration is outside this workspace.`,
        }),
      ],
    });
export { c as component };
