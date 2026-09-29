import { c as e, f as t, i as n, l as r, n as i, x as a } from "./ui-BRNtr3Vo.js";
import { t as o } from "./link-IIfPRlSn.js";
import { m as s, t as c } from "./index-BqZ61Way.js";
var l = a();
function u() {
  let { e: a, t: u } = c.useLoaderData(),
    d = s.filter((e) => e.trackId === u.id);
  return (0, l.jsxs)(`div`, {
    className: `mx-auto max-w-5xl`,
    children: [
      (0, l.jsxs)(`nav`, {
        "aria-label": `Breadcrumb`,
        className: `mb-2 text-sm`,
        children: [
          (0, l.jsx)(o, { to: `/my-courses`, className: `text-primary underline`, children: `My Courses` }),
          ` / `,
          (0, l.jsxs)(o, {
            to: `/courses/$enrolmentId`,
            params: { enrolmentId: a.id },
            className: `text-primary underline`,
            children: [a.code, ` (parent)`],
          }),
          ` / `,
          u.code,
        ],
      }),
      (0, l.jsxs)(`div`, {
        className: `mb-3 rounded-lg border bg-muted px-3 py-2 text-sm`,
        children: [(0, l.jsx)(`strong`, { children: `Parent programme:` }), ` `, a.code, ` — `, a.name, ` · `, a.curriculum],
      }),
      (0, l.jsx)(e, { title: u.name, subtitle: `${u.code} · ${u.role} · ${u.curriculum}` }),
      (0, l.jsx)(`div`, { className: `mb-4`, children: (0, l.jsx)(r, { value: u.progress, label: `Track curriculum delivered` }) }),
      d.length === 0
        ? (0, l.jsx)(t, { state: `Empty`, children: `No modules released for this track yet.` })
        : (0, l.jsx)(`ul`, {
            className: `space-y-3`,
            children: d.map((e) =>
              (0, l.jsx)(
                `li`,
                {
                  children: (0, l.jsx)(n, {
                    children: (0, l.jsxs)(`div`, {
                      className: `flex flex-wrap items-center justify-between gap-2`,
                      children: [
                        (0, l.jsx)(o, {
                          to: `/modules/$moduleId`,
                          params: { moduleId: e.id },
                          className: `font-semibold text-primary underline`,
                          children: e.title,
                        }),
                        (0, l.jsx)(i, { children: e.status }),
                      ],
                    }),
                  }),
                },
                e.id,
              ),
            ),
          }),
    ],
  });
}
export { u as component };
