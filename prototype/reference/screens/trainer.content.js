import { a as e, n as t, t as n, u as r, x as i } from "./ui-BRNtr3Vo.js";
import { t as a } from "./staff-zeGrIO0v.js";
var o = i(),
  s = () =>
    (0, o.jsxs)(a, {
      title: `Content`,
      actions: (0, o.jsx)(r, { message: `Upload would store the file in LMS content storage for review.`, children: `Upload content` }),
      children: [
        (0, o.jsx)(e, {
          caption: `Content`,
          rows: [
            { id: `1`, t: `Decision trees slides`, topic: `Decision Trees & Ensembles`, s: `Submitted for review` },
            { id: `2`, t: `Regression notes`, topic: `Linear & Logistic Regression`, s: `Approved` },
            { id: `3`, t: `Random forest lab`, topic: `Decision Trees & Ensembles`, s: `Draft` },
          ],
          getKey: (e) => e.id,
          cols: [
            { h: `Item`, c: (e) => e.t },
            { h: `Topic`, c: (e) => e.topic },
            { h: `Review state`, c: (e) => (0, o.jsx)(t, { children: e.s }) },
          ],
        }),
        (0, o.jsx)(n, { children: `Content is published to students only after Academic Coordinator review.` }),
      ],
    });
export { s as component };
