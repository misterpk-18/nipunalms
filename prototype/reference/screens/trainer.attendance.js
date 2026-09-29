import { S as e, f as t, i as n, r, w as i, x as a } from "./ui-BRNtr3Vo.js";
import { b as o } from "./index-BqZ61Way.js";
import { n as s, r as c, t as l } from "./staff-zeGrIO0v.js";
var u = i(e()),
  d = a();
function f() {
  let e = c(),
    i = o.filter((t) => s(e, t.batch)),
    [a, f] = (0, u.useState)({}),
    [p, m] = (0, u.useState)(!1);
  return (0, d.jsx)(l, {
    title: `Attendance register`,
    subtitle: `Actual Class Session: Decision trees · 28 Sep 2026`,
    children: (0, d.jsxs)(n, {
      children: [
        (0, d.jsx)(`ul`, {
          className: `divide-y`,
          children: i.map((e) =>
            (0, d.jsxs)(
              `li`,
              {
                className: `flex flex-wrap items-center justify-between gap-2 py-2`,
                children: [
                  (0, d.jsx)(`span`, { className: `text-sm font-medium`, children: e.name }),
                  (0, d.jsx)(`div`, {
                    role: `radiogroup`,
                    "aria-label": `Attendance for ${e.name}`,
                    className: `flex flex-wrap gap-1`,
                    children: [`Present`, `Absent`, `Late`].map((t) =>
                      (0, d.jsxs)(
                        `label`,
                        {
                          className: `tap flex cursor-pointer items-center gap-1 rounded-lg border px-3 text-sm ${a[e.name] === t ? `border-primary bg-accent font-semibold` : ``}`,
                          children: [
                            (0, d.jsx)(`input`, {
                              type: `radio`,
                              className: `sr-only`,
                              name: e.name,
                              checked: a[e.name] === t,
                              onChange: () => {
                                (f({ ...a, [e.name]: t }), m(!1));
                              },
                            }),
                            a[e.name] === t ? `✓ ` : ``,
                            t,
                          ],
                        },
                        t,
                      ),
                    ),
                  }),
                ],
              },
              e.name,
            ),
          ),
        }),
        (0, d.jsxs)(`div`, {
          className: `mt-3 flex flex-wrap items-center gap-3`,
          children: [
            (0, d.jsx)(r, { onClick: () => m(!0), disabled: Object.keys(a).length < i.length, children: `Confirm attendance` }),
            p
              ? (0, d.jsx)(t, { state: `Saved`, children: `Trainer-confirmed locally. Meet attendance evidence: Integration Unavailable.` })
              : (0, d.jsxs)(t, { state: `Not Submitted`, children: [i.length - Object.keys(a).length, ` student(s) unmarked.`] }),
          ],
        }),
      ],
    }),
  });
}
export { f as component };
