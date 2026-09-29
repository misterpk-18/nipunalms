import { c as e, i as t, n, x as r } from "./ui-BRNtr3Vo.js";
import { t as i } from "./link-IIfPRlSn.js";
import { a, f as o, y as s } from "./index-BqZ61Way.js";
var c = r();
function l() {
  let r = a.useLoaderData(),
    l = o[0].tracks.find((e) => e.id === r.trackId);
  return (0, c.jsxs)(`div`, {
    className: `mx-auto max-w-5xl`,
    children: [
      (0, c.jsxs)(`nav`, {
        "aria-label": `Breadcrumb`,
        className: `mb-2 text-sm`,
        children: [
          (0, c.jsx)(i, {
            to: `/courses/$enrolmentId`,
            params: { enrolmentId: `enr-001` },
            className: `text-primary underline`,
            children: `NIT-CRS-018`,
          }),
          ` / `,
          (0, c.jsx)(i, {
            to: `/courses/$enrolmentId/tracks/$trackId`,
            params: { enrolmentId: `enr-001`, trackId: l.id },
            className: `text-primary underline`,
            children: l.name,
          }),
          ` / `,
          r.title,
        ],
      }),
      (0, c.jsx)(e, { title: r.title, subtitle: `Module · ${l.curriculum}`, children: (0, c.jsx)(n, { children: r.status }) }),
      (0, c.jsx)(`ul`, {
        className: `space-y-3`,
        children: s
          .filter((e) => e.moduleId === r.id)
          .map((e) =>
            (0, c.jsx)(
              `li`,
              {
                children: (0, c.jsxs)(t, {
                  children: [
                    (0, c.jsxs)(`div`, {
                      className: `flex flex-wrap items-center justify-between gap-2`,
                      children: [
                        (0, c.jsx)(i, {
                          to: `/topics/$topicId`,
                          params: { topicId: e.id },
                          className: `font-semibold text-primary underline`,
                          children: e.title,
                        }),
                        (0, c.jsx)(n, { tone: e.required ? `info` : `neutral`, children: e.required ? `Required` : `Optional` }),
                      ],
                    }),
                    (0, c.jsxs)(`p`, {
                      className: `mt-1 text-sm text-muted-foreground`,
                      children: [e.sessions.length, ` class session(s)`],
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
export { l as component };
