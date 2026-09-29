import { c as e, f as t, i as n, l as r, n as i, t as a, x as o } from "./ui-BRNtr3Vo.js";
import { t as s } from "./link-IIfPRlSn.js";
import { f as c, x as l } from "./index-BqZ61Way.js";
var u = o();
function d() {
  let o = l();
  return (0, u.jsxs)(`div`, {
    className: `mx-auto max-w-6xl`,
    children: [
      (0, u.jsx)(e, {
        title: o(`myCourses`),
        subtitle: `One Student Master · multiple Admissions and Course Enrolments`,
        source: `LMS enrolments; Admission reference from CRM`,
      }),
      (0, u.jsx)(`div`, {
        className: `grid gap-4 md:grid-cols-2 xl:grid-cols-3`,
        children: c.map((e) =>
          (0, u.jsxs)(
            n,
            {
              className: `flex flex-col`,
              children: [
                (0, u.jsxs)(`div`, {
                  className: `flex flex-wrap gap-2`,
                  children: [(0, u.jsx)(i, { tone: `info`, children: e.kind }), (0, u.jsx)(i, { children: e.status })],
                }),
                (0, u.jsx)(`p`, { className: `mt-3 font-mono text-xs text-muted-foreground`, children: e.code }),
                (0, u.jsx)(`h2`, { className: `font-semibold`, children: e.name }),
                (0, u.jsxs)(`dl`, {
                  className: `mt-2 space-y-1 text-sm`,
                  children: [
                    (0, u.jsxs)(`div`, {
                      children: [
                        (0, u.jsx)(`dt`, { className: `inline text-muted-foreground`, children: `Service branch: ` }),
                        (0, u.jsx)(`dd`, { className: `inline`, children: e.serviceBranch }),
                      ],
                    }),
                    (0, u.jsxs)(`div`, {
                      children: [
                        (0, u.jsx)(`dt`, { className: `inline text-muted-foreground`, children: `Batch: ` }),
                        (0, u.jsx)(`dd`, { className: `inline font-mono text-xs`, children: e.batch ?? `Not allocated` }),
                      ],
                    }),
                    e.linkedTo &&
                      (0, u.jsx)(`div`, {
                        className: `text-xs text-muted-foreground`,
                        children: `Promotional complimentary — linked to qualifying paid Admission`,
                      }),
                  ],
                }),
                (0, u.jsx)(`div`, { className: `mt-3`, children: (0, u.jsx)(r, { value: e.progress, label: `Curriculum delivered` }) }),
                e.status === `Curriculum Mapping Pending` &&
                  (0, u.jsx)(`div`, {
                    className: `mt-3`,
                    children: (0, u.jsx)(t, {
                      state: `Pending Verification`,
                      children: `Curriculum Mapping Pending · Recovery Owner: Academic Coordinator — Guntur. Your Admission and receipt are preserved.`,
                    }),
                  }),
                (0, u.jsx)(s, {
                  to: `/courses/$enrolmentId`,
                  params: { enrolmentId: e.id },
                  className: `tap mt-auto inline-flex items-center pt-3 text-sm font-medium text-primary underline`,
                  children: `Open course`,
                }),
              ],
            },
            e.id,
          ),
        ),
      }),
      (0, u.jsx)(`div`, {
        className: `mt-4`,
        children: (0, u.jsx)(a, {
          children: `Your second course reuses the same student identity. Admission and finance records remain in the CRM.`,
        }),
      }),
    ],
  });
}
export { d as component };
