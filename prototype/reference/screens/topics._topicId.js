import { c as e, i as t, n, t as r, x as i } from "./ui-BRNtr3Vo.js";
import { t as a } from "./link-IIfPRlSn.js";
import { g as o, m as s, n as c } from "./index-BqZ61Way.js";
var l = i();
function u() {
  let i = c.useLoaderData(),
    u = s.find((e) => e.id === i.moduleId);
  return (0, l.jsxs)(`div`, {
    className: `mx-auto max-w-5xl`,
    children: [
      (0, l.jsxs)(`nav`, {
        "aria-label": `Breadcrumb`,
        className: `mb-2 text-sm`,
        children: [
          (0, l.jsx)(a, { to: `/modules/$moduleId`, params: { moduleId: u.id }, className: `text-primary underline`, children: u.title }),
          ` / `,
          i.title,
        ],
      }),
      (0, l.jsx)(e, {
        title: i.title,
        subtitle: `Topic`,
        children: (0, l.jsx)(n, { tone: i.required ? `info` : `neutral`, children: i.required ? `Required` : `Optional` }),
      }),
      (0, l.jsx)(t, {
        title: `Class sessions`,
        children: (0, l.jsx)(`ul`, {
          className: `divide-y`,
          children: o
            .filter((e) => e.topicId === i.id)
            .map((e) =>
              (0, l.jsxs)(
                `li`,
                {
                  className: `flex flex-wrap items-center justify-between gap-2 py-2`,
                  children: [
                    (0, l.jsx)(a, {
                      to: `/sessions/$sessionId`,
                      params: { sessionId: e.id },
                      className: `text-primary underline`,
                      children: e.title,
                    }),
                    (0, l.jsx)(`span`, { className: `text-sm text-muted-foreground`, children: e.date }),
                    (0, l.jsx)(n, { children: e.state }),
                  ],
                },
                e.id,
              ),
            ),
        }),
      }),
      (0, l.jsxs)(t, {
        className: `mt-4`,
        title: `Topic resources`,
        children: [
          (0, l.jsxs)(`ul`, {
            className: `list-disc pl-5 text-sm`,
            children: [
              (0, l.jsx)(`li`, { children: `Regression notes (PDF)` }),
              (0, l.jsx)(`li`, { children: `housing.csv dataset` }),
              (0, l.jsx)(`li`, { children: `Starter notebook (.ipynb)` }),
            ],
          }),
          (0, l.jsx)(`div`, {
            className: `mt-2`,
            children: (0, l.jsx)(r, {
              children: `Resources are one authoritative item reused across placements — no duplicate progress or files.`,
            }),
          }),
        ],
      }),
    ],
  });
}
export { u as component };
