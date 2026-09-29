import { a as e, n as t, u as n, x as r } from "./ui-BRNtr3Vo.js";
import { v as i } from "./index-BqZ61Way.js";
import { t as a } from "./staff-zeGrIO0v.js";
var o = r(),
  s = () =>
    (0, o.jsx)(a, {
      title: `Assessments`,
      actions: (0, o.jsx)(n, { message: `Question bank editor (prototype).`, children: `Build test` }),
      children: (0, o.jsx)(e, {
        caption: `Assessments`,
        rows: i,
        getKey: (e) => e.id,
        cols: [
          { h: `Title`, c: (e) => e.title },
          { h: `Type`, c: (e) => (0, o.jsx)(t, { tone: `info`, children: e.type }) },
          { h: `Duration`, c: (e) => e.duration },
          { h: `State`, c: (e) => (0, o.jsx)(t, { children: e.status }) },
        ],
      }),
    });
export { s as component };
