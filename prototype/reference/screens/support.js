import { S as e, a as t, b as n, c as r, f as i, i as a, n as o, r as s, w as c, x as l } from "./ui-BRNtr3Vo.js";
import { x as u } from "./index-BqZ61Way.js";
var d = c(e()),
  f = l(),
  p = [
    { id: `SR-1042`, cat: `Recording access`, owner: `Academic Coordinator — Guntur`, state: `Under review` },
    { id: `SR-1019`, cat: `Account / login`, owner: `LMS Support — Guntur`, state: `Completed` },
  ];
function m() {
  let e = u(),
    { lang: c } = n(),
    l = c === `te`,
    [m, h] = (0, d.useState)(``),
    [g, _] = (0, d.useState)(``),
    [v, y] = (0, d.useState)(!1),
    [b, x] = (0, d.useState)(!1);
  return (0, f.jsxs)(`div`, {
    className: `mx-auto max-w-5xl space-y-4`,
    children: [
      (0, f.jsx)(r, { title: e(`support`) }),
      (0, f.jsx)(a, {
        title: e(`raiseRequest`),
        children: (0, f.jsxs)(`form`, {
          noValidate: !0,
          className: `space-y-3`,
          onSubmit: (e) => {
            if ((e.preventDefault(), !m || !g)) {
              y(!0);
              return;
            }
            (y(!1), x(!0));
          },
          children: [
            (0, f.jsxs)(`div`, {
              children: [
                (0, f.jsx)(`label`, { htmlFor: `cat`, className: `mb-1 block text-sm font-medium`, children: l ? `వర్గం` : `Category` }),
                (0, f.jsxs)(`select`, {
                  id: `cat`,
                  value: m,
                  onChange: (e) => h(e.target.value),
                  className: `tap w-full rounded-lg border border-input bg-card px-3`,
                  children: [
                    (0, f.jsx)(`option`, { value: ``, children: l ? `ఎంచుకోండి` : `Choose` }),
                    (0, f.jsx)(`option`, { children: l ? `విద్యా సంబంధిత` : `Academic` }),
                    (0, f.jsx)(`option`, { children: `LMS` }),
                    (0, f.jsx)(`option`, { children: l ? `ఖాతా` : `Account` }),
                  ],
                }),
              ],
            }),
            (0, f.jsxs)(`div`, {
              children: [
                (0, f.jsx)(`label`, { htmlFor: `msg`, className: `mb-1 block text-sm font-medium`, children: l ? `వివరాలు` : `Details` }),
                (0, f.jsx)(`textarea`, {
                  id: `msg`,
                  rows: 3,
                  value: g,
                  onChange: (e) => _(e.target.value),
                  className: `w-full rounded-lg border border-input bg-card p-3`,
                }),
              ],
            }),
            v && (0, f.jsxs)(`p`, { role: `alert`, className: `text-sm font-medium text-danger`, children: [`⚠ `, e(`requiredField`)] }),
            (0, f.jsx)(s, { type: `submit`, children: e(`submit`) }),
            b &&
              (0, f.jsx)(i, {
                state: `Confirmation Pending`,
                children: l
                  ? `అభ్యర్థన ఈ బ్రౌజర్‌లో మాత్రమే నమోదైంది (ప్రోటోటైప్).`
                  : `Request recorded in this browser only (prototype). Owner: Academic Coordinator — Guntur.`,
              }),
          ],
        }),
      }),
      (0, f.jsx)(t, {
        caption: `My requests`,
        rows: p,
        getKey: (e) => e.id,
        cols: [
          { h: `ID`, c: (e) => e.id },
          { h: `Category`, c: (e) => e.cat },
          { h: `Named owner`, c: (e) => e.owner },
          { h: `Review state`, c: (e) => (0, f.jsx)(o, { children: e.state }) },
        ],
      }),
    ],
  });
}
export { m as component };
