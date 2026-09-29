import { c as e, i as t, n, t as r, x as i } from "./ui-BRNtr3Vo.js";
import { t as a } from "./link-IIfPRlSn.js";
import { C as o, v as s, w as c, x as l } from "./index-BqZ61Way.js";
var u = i();
function d() {
  let i = l();
  return o({ select: (e) => e.location.pathname }) === `/tests`
    ? (0, u.jsxs)(`div`, {
        className: `mx-auto max-w-5xl`,
        children: [
          (0, u.jsx)(e, { title: i(`tests`), source: `LMS assessments` }),
          (0, u.jsx)(`ul`, {
            className: `grid gap-3 md:grid-cols-2`,
            children: s.map((e) =>
              (0, u.jsx)(
                `li`,
                {
                  children: (0, u.jsxs)(t, {
                    children: [
                      (0, u.jsxs)(`div`, {
                        className: `flex flex-wrap gap-2`,
                        children: [(0, u.jsx)(n, { tone: `info`, children: e.type }), (0, u.jsx)(n, { children: e.status })],
                      }),
                      (0, u.jsx)(a, {
                        to: `/tests/$id`,
                        params: { id: e.id },
                        className: `mt-2 block font-semibold text-primary underline`,
                        children: e.title,
                      }),
                      (0, u.jsxs)(`p`, { className: `text-sm text-muted-foreground`, children: [`Duration `, e.duration] }),
                    ],
                  }),
                },
                e.id,
              ),
            ),
          }),
          (0, u.jsx)(`div`, {
            className: `mt-4`,
            children: (0, u.jsx)(r, {
              children: `Completing an assessment does not equal attendance, course completion or certificate issue.`,
            }),
          }),
        ],
      })
    : (0, u.jsx)(c, {});
}
export { d as component };
