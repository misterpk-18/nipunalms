import { a as e, n as t, u as n, x as r } from "./ui-BRNtr3Vo.js";
import { c as i } from "./index-BqZ61Way.js";
import { t as a } from "./staff-zeGrIO0v.js";
var o = r(),
  s = () =>
    (0, o.jsx)(a, {
      title: `Assignments`,
      actions: (0, o.jsx)(n, { message: `New assignment draft (prototype).`, children: `New assignment` }),
      children: (0, o.jsx)(e, {
        caption: `Assignments`,
        rows: i,
        getKey: (e) => e.id,
        cols: [
          { h: `Title`, c: (e) => e.title },
          { h: `Topic`, c: (e) => e.topic },
          { h: `Type`, c: (e) => (0, o.jsx)(t, { tone: e.required ? `info` : `neutral`, children: e.required ? `Required` : `Optional` }) },
          { h: `Due`, c: (e) => e.due },
          { h: `State`, c: (e) => (0, o.jsx)(t, { children: e.view }) },
        ],
      }),
    });
export { s as component };
