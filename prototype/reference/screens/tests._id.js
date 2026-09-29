import { S as e, c as t, f as n, i as r, n as i, r as a, t as o, w as s, x as c } from "./ui-BRNtr3Vo.js";
import { t as l } from "./link-IIfPRlSn.js";
import { r as u, v as d } from "./index-BqZ61Way.js";
var f = s(e()),
  p = c(),
  m = `tap w-full rounded-lg border border-input bg-card px-3`;
function h({ n: e, type: t, children: n }) {
  return (0, p.jsxs)(`fieldset`, {
    className: `rounded-xl border bg-card p-4`,
    children: [
      (0, p.jsxs)(`legend`, {
        className: `px-1 text-sm font-semibold`,
        children: [`Q`, e, ` · `, (0, p.jsx)(`span`, { className: `text-muted-foreground`, children: t })],
      }),
      n,
    ],
  });
}
function g() {
  let e = u.useLoaderData(),
    [s, c] = (0, f.useState)(`Saved`),
    [g, _] = (0, f.useState)(null);
  return (0, p.jsxs)(`div`, {
    className: `mx-auto max-w-4xl`,
    children: [
      (0, p.jsxs)(`nav`, {
        className: `mb-2 text-sm`,
        children: [(0, p.jsx)(l, { to: `/tests`, className: `text-primary underline`, children: `Tests` }), ` / `, e.title],
      }),
      (0, p.jsx)(t, { title: e.title, children: (0, p.jsx)(i, { tone: `info`, children: e.type }) }),
      (0, p.jsxs)(`div`, {
        className: `sticky top-[90px] z-30 mb-4 flex flex-wrap items-center gap-3 rounded-xl border bg-card p-3 shadow-sm`,
        children: [
          (0, p.jsx)(`span`, { className: `font-mono text-lg font-semibold`, "aria-label": `Time remaining`, children: `18:42` }),
          (0, p.jsx)(`span`, {
            className: `text-xs text-muted-foreground`,
            children: `Server-authoritative timer (concept) — closing the tab does not pause time.`,
          }),
          (0, p.jsx)(`div`, { className: `ml-auto`, children: (0, p.jsx)(n, { state: s }) }),
        ],
      }),
      (0, p.jsxs)(`form`, {
        className: `space-y-4`,
        onChange: () => {
          (c(`Saving`), setTimeout(() => c(`Saved`), 500));
        },
        onSubmit: (t) => {
          (t.preventDefault(), _(`RCPT-T-` + String(1e3 + d.indexOf(e))));
        },
        children: [
          (0, p.jsxs)(h, {
            n: 1,
            type: `Single-answer MCQ`,
            children: [
              (0, p.jsx)(`p`, { className: `mb-2 text-sm`, children: `Which metric suits an imbalanced binary classifier?` }),
              [`Accuracy`, `F1-score`, `R²`].map((e) =>
                (0, p.jsxs)(
                  `label`,
                  { className: `tap flex items-center gap-2`, children: [(0, p.jsx)(`input`, { type: `radio`, name: `q1` }), ` `, e] },
                  e,
                ),
              ),
            ],
          }),
          (0, p.jsxs)(h, {
            n: 2,
            type: `Multiple-answer MCQ`,
            children: [
              (0, p.jsx)(`p`, { className: `mb-2 text-sm`, children: `Select all regularisation methods.` }),
              [`L1 (Lasso)`, `L2 (Ridge)`, `One-hot encoding`].map((e) =>
                (0, p.jsxs)(
                  `label`,
                  { className: `tap flex items-center gap-2`, children: [(0, p.jsx)(`input`, { type: `checkbox` }), ` `, e] },
                  e,
                ),
              ),
            ],
          }),
          (0, p.jsxs)(h, {
            n: 3,
            type: `True / False`,
            children: [
              (0, p.jsx)(`p`, { className: `mb-2 text-sm`, children: `Logistic regression outputs probabilities.` }),
              [`True`, `False`].map((e) =>
                (0, p.jsxs)(
                  `label`,
                  { className: `tap flex items-center gap-2`, children: [(0, p.jsx)(`input`, { type: `radio`, name: `q3` }), ` `, e] },
                  e,
                ),
              ),
            ],
          }),
          (0, p.jsxs)(h, {
            n: 4,
            type: `Numeric`,
            children: [
              (0, p.jsx)(`label`, { className: `text-sm`, htmlFor: `q4`, children: `Slope for y = 3x + 2?` }),
              (0, p.jsx)(`input`, { id: `q4`, inputMode: `decimal`, className: m }),
            ],
          }),
          (0, p.jsxs)(h, {
            n: 5,
            type: `Short answer`,
            children: [
              (0, p.jsx)(`label`, { className: `text-sm`, htmlFor: `q5`, children: `Name one ensemble method.` }),
              (0, p.jsx)(`input`, { id: `q5`, className: m }),
            ],
          }),
          (0, p.jsxs)(h, {
            n: 6,
            type: `Descriptive`,
            children: [
              (0, p.jsx)(`label`, { className: `text-sm`, htmlFor: `q6`, children: `Explain bias–variance trade-off.` }),
              (0, p.jsx)(`textarea`, { id: `q6`, rows: 3, className: `w-full rounded-lg border border-input bg-card p-3` }),
            ],
          }),
          (0, p.jsxs)(h, {
            n: 7,
            type: `Coding`,
            children: [
              (0, p.jsx)(`label`, { className: `text-sm`, htmlFor: `q7`, children: `Write a function returning the mean of a list.` }),
              (0, p.jsx)(`textarea`, {
                id: `q7`,
                rows: 5,
                spellCheck: !1,
                defaultValue: `def mean(xs):
    `,
                className: `w-full rounded-lg border border-input bg-navy p-3 font-mono text-sm text-navy-foreground`,
              }),
              (0, p.jsx)(`p`, {
                className: `mt-1 text-xs text-muted-foreground`,
                children: `Code execution sandbox: Not Configured in prototype.`,
              }),
            ],
          }),
          (0, p.jsxs)(h, {
            n: 8,
            type: `Output prediction`,
            children: [
              (0, p.jsxs)(`pre`, {
                className: `mb-2 rounded bg-muted p-2 font-mono text-sm`,
                children: [`print(len(`, `{`, `1, 1, 2`, `}`, `))`],
              }),
              (0, p.jsx)(`label`, { className: `text-sm`, htmlFor: `q8`, children: `Predicted output` }),
              (0, p.jsx)(`input`, { id: `q8`, className: m }),
            ],
          }),
          (0, p.jsxs)(`div`, {
            className: `flex flex-wrap gap-2`,
            children: [
              (0, p.jsx)(a, { type: `submit`, children: `Submit test` }),
              (0, p.jsx)(a, { variant: `outline`, onClick: () => c(`Failed`), children: `Simulate connection drop` }),
            ],
          }),
        ],
      }),
      s === `Failed` &&
        (0, p.jsx)(`div`, {
          className: `mt-3`,
          children: (0, p.jsxs)(n, {
            state: `Failed`,
            children: [
              `Connection interrupted. `,
              (0, p.jsx)(`strong`, { children: `Interrupted Recovery:` }),
              ` your last saved answers (sample) will be restored when you reconnect; the server timer continues.`,
            ],
          }),
        }),
      g &&
        (0, p.jsx)(r, {
          className: `mt-4`,
          title: `Submission Receipt`,
          children: (0, p.jsxs)(`p`, {
            className: `text-sm`,
            children: [`Receipt `, g, ` · 26 Sep 2026 10:34 IST (prototype, stored locally only).`],
          }),
        }),
      (0, p.jsx)(`div`, {
        className: `mt-4`,
        children: (0, p.jsx)(o, { children: `Assessment completion does not equal attendance, course completion or certificate issue.` }),
      }),
    ],
  });
}
export { g as component };
