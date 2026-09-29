import { a as e, n as t, u as n, x as r } from "./ui-BRNtr3Vo.js";
import { t as i } from "./staff-zeGrIO0v.js";
var a = r(),
  o = [
    { id: `c1`, item: `Decision trees slides`, by: `Trainer M. Demo`, topic: `Decision Trees & Ensembles`, s: `Submitted for review` },
    { id: `c2`, item: `Random forest lab`, by: `Trainer M. Demo`, topic: `Decision Trees & Ensembles`, s: `Changes requested` },
    { id: `c3`, item: `AWS IAM lab`, by: `Trainer S. Example`, topic: `AWS orientation`, s: `Submitted for review` },
  ],
  s = () =>
    (0, a.jsx)(i, {
      title: `Content Review`,
      children: (0, a.jsx)(e, {
        caption: `Content review queue`,
        rows: o,
        getKey: (e) => e.id,
        cols: [
          { h: `Item`, c: (e) => e.item },
          { h: `Submitted by`, c: (e) => e.by },
          { h: `Topic`, c: (e) => e.topic },
          { h: `State`, c: (e) => (0, a.jsx)(t, { children: e.s }) },
          {
            h: `Action`,
            c: () => (0, a.jsx)(n, { variant: `outline`, message: `Approve & release to mapped topics.`, children: `Approve` }),
          },
        ],
      }),
    });
export { s as component };
