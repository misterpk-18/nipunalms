import { S as e, b as t, c as n, d as r, f as i, i as a, n as o, o as s, r as c, t as l, u, w as d, x as f } from "./ui-BRNtr3Vo.js";
import { t as p } from "./link-IIfPRlSn.js";
import { g as m, p as h } from "./index-BqZ61Way.js";
var g = d(e()),
  _ = f(),
  v = [`Open today's session`, `Join / Start Meet`, `Record delivered topics`, `Mark attendance`, `Notes & closeout`];
function y() {
  let { role: e, notify: d } = t(),
    f = e.branch,
    y = m.filter((e) => e.branch === f && e.state === `Scheduled`),
    b = y[0],
    [x, S] = (0, g.useState)(0),
    [C, w] = (0, g.useState)([]);
  return (0, _.jsxs)(`div`, {
    className: `mx-auto max-w-6xl`,
    children: [
      (0, _.jsx)(n, { title: `Today`, subtitle: `${e.label} · scope: assigned batches & students only`, source: `LMS assigned sessions` }),
      (0, _.jsxs)(s, {
        cols: 3,
        children: [
          (0, _.jsx)(r, { rank: 1, label: `Assigned sessions scheduled`, value: y.length, hint: `Next 7 days` }),
          (0, _.jsx)(r, { rank: 2, label: `Submissions awaiting my review`, value: f === `Guntur` ? 4 : 1, hint: `Oldest: 6 days` }),
          (0, _.jsx)(r, { rank: 3, label: `Assigned students with open support flags`, value: f === `Guntur` ? 2 : 1 }),
        ],
      }),
      b
        ? (0, _.jsxs)(a, {
            className: `mt-6`,
            title: `Today's flow — ${b.title}`,
            children: [
              (0, _.jsxs)(`p`, {
                className: `mb-3 text-sm text-muted-foreground`,
                children: [
                  b.date,
                  ` · `,
                  b.time,
                  ` · `,
                  (0, _.jsx)(`span`, { className: `font-mono text-xs`, children: b.batch }),
                  ` · Meet organizer label: `,
                  h[f],
                  ` `,
                  (0, _.jsx)(o, { children: `Pending Verification` }),
                ],
              }),
              (0, _.jsx)(`ol`, {
                className: `mb-4 grid gap-2 sm:grid-cols-5`,
                children: v.map((e, t) =>
                  (0, _.jsxs)(
                    `li`,
                    {
                      className: `rounded-lg border p-2 text-sm ${t === x ? `border-primary bg-accent font-semibold` : t < x ? `bg-success-soft` : ``}`,
                      children: [
                        (0, _.jsx)(`span`, { className: `text-xs`, children: t < x ? `✓ Done` : `Step ${t + 1}` }),
                        (0, _.jsx)(`br`, {}),
                        e,
                      ],
                    },
                    e,
                  ),
                ),
              }),
              x === 0 && (0, _.jsx)(c, { onClick: () => S(1), children: `Open session` }),
              x === 1 &&
                (0, _.jsxs)(`div`, {
                  className: `flex flex-wrap gap-2`,
                  children: [
                    (0, _.jsx)(u, { message: `Start Meet would open Google Meet as the branch organizer.`, children: `Join / Start Meet` }),
                    (0, _.jsx)(c, { variant: `outline`, onClick: () => S(2), children: `Continue (class started)` }),
                  ],
                }),
              x === 2 &&
                (0, _.jsxs)(`fieldset`, {
                  children: [
                    (0, _.jsx)(`legend`, {
                      className: `mb-2 text-sm font-medium`,
                      children: `Topics delivered in this actual Class Session`,
                    }),
                    [`Decision tree splitting (Gini/entropy)`, `Pruning`, `Random forest intro`].map((e) =>
                      (0, _.jsxs)(
                        `label`,
                        {
                          className: `tap flex items-center gap-2 text-sm`,
                          children: [
                            (0, _.jsx)(`input`, {
                              type: `checkbox`,
                              checked: C.includes(e),
                              onChange: (t) => w(t.target.checked ? [...C, e] : C.filter((t) => t !== e)),
                            }),
                            e,
                          ],
                        },
                        e,
                      ),
                    ),
                    (0, _.jsx)(c, { className: `mt-2`, disabled: !C.length, onClick: () => S(3), children: `Save delivered topics` }),
                  ],
                }),
              x === 3 &&
                (0, _.jsxs)(`div`, {
                  className: `space-y-2`,
                  children: [
                    (0, _.jsxs)(`p`, {
                      className: `text-sm`,
                      children: [
                        `Mark attendance in the `,
                        (0, _.jsx)(p, { to: `/trainer/attendance`, className: `text-primary underline`, children: `attendance register` }),
                        `, or continue.`,
                      ],
                    }),
                    (0, _.jsx)(c, { onClick: () => S(4), children: `Attendance confirmed` }),
                  ],
                }),
              x === 4 &&
                (0, _.jsxs)(`div`, {
                  className: `space-y-2`,
                  children: [
                    (0, _.jsx)(`label`, { htmlFor: `notes`, className: `block text-sm font-medium`, children: `Session notes` }),
                    (0, _.jsx)(`textarea`, { id: `notes`, rows: 3, className: `w-full rounded-lg border border-input bg-card p-3` }),
                    (0, _.jsx)(c, {
                      onClick: () => {
                        (S(5), d(`Closeout saved locally only. Recording mapping stays Pending Verification.`, `info`));
                      },
                      children: `Close out session`,
                    }),
                  ],
                }),
              x === 5 &&
                (0, _.jsx)(i, { state: `Saved`, children: `Session closed out locally. Recording mapping: Pending Verification.` }),
            ],
          })
        : (0, _.jsx)(`div`, {
            className: `mt-6`,
            children: (0, _.jsx)(i, { state: `Empty`, children: `No assigned session scheduled today.` }),
          }),
      (0, _.jsx)(`div`, {
        className: `mt-4`,
        children: (0, _.jsx)(l, {
          children: `Trainers see only assigned batches and students. No leads, finance, refunds or global Course Master administration.`,
        }),
      }),
    ],
  });
}
export { y as component };
