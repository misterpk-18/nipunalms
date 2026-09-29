import { S as e, f as t, i as n, n as r, r as i, w as a, x as o } from "./ui-BRNtr3Vo.js";
import { t as s } from "./staff-zeGrIO0v.js";
var c = a(e()),
  l = o(),
  u = [
    { id: `s1`, who: `Sample Student — Anvitha K.`, item: `EDA mini report`, ver: `v1 · 19 Sep` },
    { id: `s2`, who: `Sample Learner G.`, item: `Regression on housing dataset`, ver: `v1 · 25 Sep` },
    { id: `s3`, who: `Sample Learner H.`, item: `Regression on housing dataset`, ver: `v2 · 26 Sep` },
  ];
function d() {
  let [e, a] = (0, c.useState)({});
  return (0, l.jsx)(s, {
    title: `Submissions awaiting my review`,
    children: u.map((o) =>
      (0, l.jsxs)(
        n,
        {
          title: `${o.item} — ${o.who}`,
          action: (0, l.jsx)(r, { children: e[o.id] ? `Reviewed (local)` : `Under Review` }),
          children: [
            (0, l.jsxs)(`p`, { className: `text-sm text-muted-foreground`, children: [`Submission `, o.ver] }),
            (0, l.jsxs)(`div`, {
              className: `mt-2 grid gap-2 sm:grid-cols-[1fr_8rem]`,
              children: [
                (0, l.jsxs)(`div`, {
                  children: [
                    (0, l.jsx)(`label`, { htmlFor: `fb-${o.id}`, className: `text-sm font-medium`, children: `Feedback` }),
                    (0, l.jsx)(`textarea`, { id: `fb-${o.id}`, rows: 2, className: `w-full rounded-lg border border-input bg-card p-2` }),
                  ],
                }),
                (0, l.jsxs)(`div`, {
                  children: [
                    (0, l.jsx)(`label`, { htmlFor: `mk-${o.id}`, className: `text-sm font-medium`, children: `Marks / 20` }),
                    (0, l.jsx)(`input`, {
                      id: `mk-${o.id}`,
                      inputMode: `numeric`,
                      className: `tap w-full rounded-lg border border-input bg-card px-3`,
                    }),
                  ],
                }),
              ],
            }),
            (0, l.jsxs)(`div`, {
              className: `mt-2 flex flex-wrap items-center gap-2`,
              children: [
                (0, l.jsx)(i, { onClick: () => a({ ...e, [o.id]: !0 }), children: `Save review` }),
                e[o.id] && (0, l.jsx)(t, { state: `Saved`, children: `Result remains provisional until published.` }),
              ],
            }),
          ],
        },
        o.id,
      ),
    ),
  });
}
export { d as component };
