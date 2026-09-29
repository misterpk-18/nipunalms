import { S as e, c as t, f as n, i as r, n as i, p as a, w as o, x as s } from "./ui-BRNtr3Vo.js";
import { t as c } from "./link-IIfPRlSn.js";
import { C as l, c as u, w as d, x as f } from "./index-BqZ61Way.js";
var p = o(e()),
  m = s(),
  h = [`Upcoming`, `Due`, `Submitted`, `Under Review`, `Reviewed`];
function g() {
  let e = f(),
    o = l({ select: (e) => e.location.pathname }),
    [s, g] = (0, p.useState)(`Due`);
  if (o !== `/assignments`) return (0, m.jsx)(d, {});
  let _ = u.filter((e) => e.view === s);
  return (0, m.jsxs)(`div`, {
    className: `mx-auto max-w-5xl`,
    children: [
      (0, m.jsx)(t, { title: e(`assignments`), source: `LMS assignments` }),
      (0, m.jsx)(a, { tabs: h, value: s, onChange: g, label: `Assignment views` }),
      _.length === 0
        ? (0, m.jsx)(n, { state: `Empty` })
        : (0, m.jsx)(`ul`, {
            className: `space-y-3`,
            children: _.map((e) =>
              (0, m.jsx)(
                `li`,
                {
                  children: (0, m.jsxs)(r, {
                    children: [
                      (0, m.jsxs)(`div`, {
                        className: `flex flex-wrap gap-2`,
                        children: [
                          (0, m.jsx)(i, { tone: e.required ? `info` : `neutral`, children: e.required ? `Required` : `Optional` }),
                          (0, m.jsx)(i, { children: e.view }),
                        ],
                      }),
                      (0, m.jsx)(c, {
                        to: `/assignments/$id`,
                        params: { id: e.id },
                        className: `mt-2 block font-semibold text-primary underline`,
                        children: e.title,
                      }),
                      (0, m.jsxs)(`p`, {
                        className: `text-sm text-muted-foreground`,
                        children: [e.module, ` → `, e.topic, ` · Due `, e.due],
                      }),
                    ],
                  }),
                },
                e.id,
              ),
            ),
          }),
    ],
  });
}
export { g as component };
