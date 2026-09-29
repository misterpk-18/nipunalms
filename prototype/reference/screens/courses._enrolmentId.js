import { c as e, f as t, i as n, l as r, n as i, s as a, t as o, x as s } from "./ui-BRNtr3Vo.js";
import { t as c } from "./link-IIfPRlSn.js";
import { C as l, o as u, w as d } from "./index-BqZ61Way.js";
var f = s();
function p() {
  let s = u.useLoaderData();
  return l({ select: (e) => e.location.pathname }).includes(`/tracks/`)
    ? (0, f.jsx)(d, {})
    : (0, f.jsxs)(`div`, {
        className: `mx-auto max-w-6xl`,
        children: [
          (0, f.jsxs)(`nav`, {
            "aria-label": `Breadcrumb`,
            className: `mb-2 text-sm`,
            children: [(0, f.jsx)(c, { to: `/my-courses`, className: `text-primary underline`, children: `My Courses` }), ` / `, s.code],
          }),
          (0, f.jsx)(e, { title: s.name, subtitle: `${s.code} · ${s.kind}`, source: `LMS course enrolment; Admission ref from CRM` }),
          (0, f.jsxs)(`div`, {
            className: `grid gap-4 lg:grid-cols-3`,
            children: [
              (0, f.jsx)(n, {
                title: `Enrolment details`,
                className: `lg:col-span-2`,
                children: (0, f.jsx)(a, {
                  items: [
                    [`Admission reference (CRM)`, s.admissionRef],
                    [`Service branch`, s.serviceBranch],
                    [`Collecting branch (CRM)`, s.collectingBranch],
                    [`Batch`, s.batch ?? `Not allocated`],
                    [`Trainer(s)`, s.trainers.length ? s.trainers.join(`, `) : `Not assigned`],
                    [`Curriculum version`, s.curriculum ?? `Curriculum Mapping Pending`],
                    [`Delivery mode`, s.mode],
                    [`Joining Date`, s.joiningDate ?? `Pending — first confirmed regular class`],
                    [
                      `Recording / material access until`,
                      s.joiningDate
                        ? `12 Jan 2027 (1 year) · extendable once on request to 12 Jan 2028`
                        : `Pending — starts from confirmed Joining Date`,
                    ],
                    [`Certificate status`, (0, f.jsx)(i, { children: s.certificate }, `c`)],
                    [`Support`, `Academic Coordinator — ` + s.serviceBranch],
                  ],
                }),
              }),
              (0, f.jsxs)(`div`, {
                className: `space-y-4`,
                children: [
                  (0, f.jsxs)(n, {
                    title: `Progress`,
                    children: [
                      (0, f.jsx)(r, { value: s.progress, label: `Curriculum delivered` }),
                      (0, f.jsx)(c, {
                        to: `/progress`,
                        className: `mt-2 inline-block text-sm text-primary underline`,
                        children: `See all four measures`,
                      }),
                    ],
                  }),
                  (0, f.jsxs)(n, {
                    title: `Finance summary (read-only)`,
                    children: [
                      (0, f.jsx)(`p`, {
                        className: `text-sm`,
                        children: `Admission fee: ₹ 84,000 · Verified receipts: ₹ 42,000 · Due: ₹ 42,000`,
                      }),
                      (0, f.jsx)(`p`, {
                        className: `mt-1 text-xs text-muted-foreground`,
                        children: `Shown only where permitted. CRM is authoritative.`,
                      }),
                      (0, f.jsx)(c, { to: `/finance`, className: `text-sm text-primary underline`, children: `Fees & receipts` }),
                    ],
                  }),
                ],
              }),
            ],
          }),
          s.tracks &&
            (0, f.jsx)(n, {
              className: `mt-4`,
              title: `Combo programme — one paid Admission · 3 main tracks + included booster`,
              children: (0, f.jsx)(`ul`, {
                className: `grid gap-3 md:grid-cols-2`,
                children: s.tracks.map((e) =>
                  (0, f.jsxs)(
                    `li`,
                    {
                      className: `rounded-lg border p-3`,
                      children: [
                        (0, f.jsxs)(`div`, {
                          className: `flex flex-wrap gap-2`,
                          children: [
                            (0, f.jsx)(i, { tone: e.role === `Included booster` ? `sim` : `info`, children: e.role }),
                            (0, f.jsx)(`span`, { className: `font-mono text-xs`, children: e.code }),
                          ],
                        }),
                        (0, f.jsx)(`p`, { className: `mt-1 font-medium`, children: e.name }),
                        (0, f.jsx)(`div`, { className: `mt-2`, children: (0, f.jsx)(r, { value: e.progress, label: `Delivered` }) }),
                        (0, f.jsx)(c, {
                          to: `/courses/$enrolmentId/tracks/$trackId`,
                          params: { enrolmentId: s.id, trackId: e.id },
                          className: `tap mt-1 inline-flex items-center text-sm text-primary underline`,
                          children: `Open track`,
                        }),
                      ],
                    },
                    e.id,
                  ),
                ),
              }),
            }),
          !s.curriculum &&
            (0, f.jsx)(`div`, {
              className: `mt-4`,
              children: (0, f.jsx)(t, {
                state: `Pending Verification`,
                children: `Curriculum Mapping Pending — Recovery Owner: Academic Coordinator — Guntur.`,
              }),
            }),
          (0, f.jsx)(`div`, {
            className: `mt-4`,
            children: (0, f.jsx)(o, {
              children: `Hierarchy: My Course / Combo → Track → Module → Topic → Session resources. Shared content is not duplicated between tracks.`,
            }),
          }),
        ],
      });
}
export { p as component };
