import { S as e, c as t, f as n, i as r, n as i, r as a, s as o, w as s, x as c } from "./ui-BRNtr3Vo.js";
import { t as l } from "./link-IIfPRlSn.js";
import { s as u, x as d } from "./index-BqZ61Way.js";
var f = s(e()),
  p = c();
function m() {
  let e = u.useLoaderData(),
    s = d(),
    [c, m] = (0, f.useState)(`Not Submitted`),
    [h, g] = (0, f.useState)(``);
  return (0, p.jsxs)(`div`, {
    className: `mx-auto max-w-4xl`,
    children: [
      (0, p.jsxs)(`nav`, {
        className: `mb-2 text-sm`,
        children: [(0, p.jsx)(l, { to: `/assignments`, className: `text-primary underline`, children: s(`assignments`) }), ` / `, e.title],
      }),
      (0, p.jsxs)(t, {
        title: e.title,
        children: [
          (0, p.jsx)(i, { tone: e.required ? `info` : `neutral`, children: e.required ? `Required` : `Optional` }),
          (0, p.jsx)(i, { children: e.view }),
        ],
      }),
      (0, p.jsxs)(r, {
        children: [
          (0, p.jsx)(o, {
            items: [
              [`Module → Topic`, `${e.module} → ${e.topic}`],
              [`Released`, e.release],
              [`Due`, e.due],
              [`Submission version`, e.version],
              [`Feedback`, e.feedback],
              [`Marks / result`, e.marks],
            ],
          }),
          (0, p.jsxs)(`p`, {
            className: `mt-4 text-sm`,
            children: [
              (0, p.jsx)(`strong`, { children: `Brief:` }),
              ` Build and evaluate a model on the provided dataset; include a short write-up of assumptions. Resources: housing.csv, starter notebook.`,
            ],
          }),
        ],
      }),
      (e.view === `Due` || e.view === `Upcoming`) &&
        (0, p.jsxs)(r, {
          className: `mt-4`,
          title: `Your submission (prototype)`,
          children: [
            (0, p.jsx)(`label`, { htmlFor: `sub`, className: `mb-1 block text-sm font-medium`, children: `Notes / link to your work` }),
            (0, p.jsx)(`textarea`, {
              id: `sub`,
              value: h,
              onChange: (e) => g(e.target.value),
              rows: 4,
              className: `w-full rounded-lg border border-input bg-card p-3`,
            }),
            (0, p.jsxs)(`div`, {
              className: `mt-3 flex flex-wrap items-center gap-3`,
              children: [
                (0, p.jsxs)(a, {
                  onClick: () => {
                    (m(`Saving`), setTimeout(() => m(`Saved`), 700));
                  },
                  disabled: !h,
                  children: [s(`submit`), ` (save locally)`],
                }),
                (0, p.jsx)(n, {
                  state: c,
                  children: c === `Saved` ? `Saved in this browser only — not delivered to any LMS server.` : void 0,
                }),
              ],
            }),
          ],
        }),
    ],
  });
}
export { m as component };
