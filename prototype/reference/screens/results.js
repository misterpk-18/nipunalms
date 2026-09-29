import { a as e, c as t, n, t as r, x as i } from "./ui-BRNtr3Vo.js";
import { x as a } from "./index-BqZ61Way.js";
var o = i(),
  s = [
    { id: `1`, item: `SQL window functions set`, score: `18 / 20`, state: `Published` },
    { id: `2`, item: `SQL coding exercise`, score: `Withheld until publication`, state: `Provisional — pending moderation` },
    { id: `3`, item: `Python Foundations module test`, score: `42 / 50`, state: `Published` },
    { id: `4`, item: `EDA mini report`, score: `—`, state: `Pending review` },
  ];
function c() {
  let i = a();
  return (0, o.jsxs)(`div`, {
    className: `mx-auto max-w-4xl`,
    children: [
      (0, o.jsx)(t, { title: i(`results`), source: `LMS published results` }),
      (0, o.jsx)(e, {
        caption: `Results`,
        rows: s,
        getKey: (e) => e.id,
        cols: [
          { h: `Assessment`, c: (e) => e.item },
          { h: `Score`, c: (e) => e.score },
          { h: `State`, c: (e) => (0, o.jsx)(n, { children: e.state }) },
        ],
      }),
      (0, o.jsx)(`div`, {
        className: `mt-4`,
        children: (0, o.jsx)(r, { children: `Only Published results are final. Provisional marks are not shown as scores.` }),
      }),
    ],
  });
}
export { c as component };
