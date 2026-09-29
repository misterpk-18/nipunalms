import { c as e, i as t, n, u as r, x as i } from "./ui-BRNtr3Vo.js";
import { t as a } from "./link-IIfPRlSn.js";
import { g as o, x as s } from "./index-BqZ61Way.js";
var c = i();
function l() {
  let i = s(),
    l = o.filter((e) => e.state === `Scheduled`);
  return (0, c.jsxs)(`div`, {
    className: `mx-auto max-w-4xl`,
    children: [
      (0, c.jsx)(e, { title: i(`schedule`), subtitle: `All times in IST (Asia/Kolkata)`, source: `LMS scheduled Class Sessions` }),
      (0, c.jsx)(`ul`, {
        className: `space-y-3`,
        children: l.map((e) =>
          (0, c.jsx)(
            `li`,
            {
              children: (0, c.jsxs)(t, {
                children: [
                  (0, c.jsxs)(`div`, {
                    className: `flex flex-wrap items-start justify-between gap-2`,
                    children: [
                      (0, c.jsxs)(`div`, {
                        children: [
                          (0, c.jsxs)(`p`, { className: `text-sm font-semibold text-primary`, children: [e.date, ` · `, e.time] }),
                          (0, c.jsx)(a, {
                            to: `/sessions/$sessionId`,
                            params: { sessionId: e.id },
                            className: `font-semibold underline`,
                            children: e.title,
                          }),
                          (0, c.jsxs)(`p`, {
                            className: `text-sm text-muted-foreground`,
                            children: [
                              e.mode,
                              ` · `,
                              e.trainer,
                              ` · `,
                              e.branch,
                              ` · `,
                              (0, c.jsx)(`span`, { className: `font-mono text-xs`, children: e.batch }),
                            ],
                          }),
                        ],
                      }),
                      (0, c.jsx)(n, { children: e.state }),
                    ],
                  }),
                  (0, c.jsx)(`div`, {
                    className: `mt-3`,
                    children: (0, c.jsx)(r, {
                      message: `Join Class would open Google Meet (organizer Pending Verification).`,
                      children: i(`joinClass`),
                    }),
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
