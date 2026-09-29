import { a as e, n as t, x as n } from "./ui-BRNtr3Vo.js";
import { t as r } from "./staff-zeGrIO0v.js";
var i = n(),
  a = [
    {
      id: `SR-1042`,
      who: `Sample Student — Anvitha K.`,
      cat: `Recording access`,
      owner: `Academic Coordinator — Guntur`,
      s: `Under review`,
    },
    { id: `SR-1051`, who: `Sample Learner G.`, cat: `Attendance recovery`, owner: `Academic Coordinator — Guntur`, s: `Awaiting trainer` },
    { id: `SR-1060`, who: `Sample Learner J.`, cat: `Device access`, owner: `LMS Support — Vijayawada`, s: `Open` },
  ],
  o = () =>
    (0, i.jsx)(r, {
      title: `Academic Support`,
      children: (0, i.jsx)(e, {
        caption: `Support requests`,
        rows: a,
        getKey: (e) => e.id,
        cols: [
          { h: `ID`, c: (e) => e.id },
          { h: `Student`, c: (e) => e.who },
          { h: `Category`, c: (e) => e.cat },
          { h: `Owner`, c: (e) => e.owner },
          { h: `State`, c: (e) => (0, i.jsx)(t, { children: e.s }) },
        ],
      }),
    });
export { o as component };
