import { c as e, f as t, i as n, n as r, s as i, u as a, x as o } from "./ui-BRNtr3Vo.js";
import { t as s } from "./link-IIfPRlSn.js";
import { i as c, p as l, y as u } from "./index-BqZ61Way.js";
var d = o();
function f() {
  let o = c.useLoaderData(),
    f = u.find((e) => e.id === o.topicId);
  return (0, d.jsxs)(`div`, {
    className: `mx-auto max-w-5xl`,
    children: [
      (0, d.jsxs)(`nav`, {
        "aria-label": `Breadcrumb`,
        className: `mb-2 text-sm`,
        children: [
          f && (0, d.jsx)(s, { to: `/topics/$topicId`, params: { topicId: f.id }, className: `text-primary underline`, children: f.title }),
          ` / `,
          o.title,
        ],
      }),
      (0, d.jsx)(e, { title: o.title, subtitle: `Actual Class Session · ${o.id}`, children: (0, d.jsx)(r, { children: o.state }) }),
      (0, d.jsxs)(n, {
        children: [
          (0, d.jsx)(i, {
            items: [
              [`Date / time`, `${o.date} · ${o.time}`],
              [`Mode`, o.mode],
              [`Trainer`, o.trainer],
              [`Branch`, o.branch],
              [`Batch`, o.batch],
              [`Meet organizer (label)`, `${l[o.branch]} — Pending Verification`],
              [`Recording`, (0, d.jsx)(r, { children: o.recording }, `r`)],
              [`My attendance`, (0, d.jsx)(r, { children: o.attendance }, `a`)],
            ],
          }),
          (0, d.jsxs)(`div`, {
            className: `mt-4 flex flex-wrap gap-2`,
            children: [
              (0, d.jsx)(a, { message: `Join Class would open the associated Google Meet.`, children: `Join Class` }),
              (0, d.jsx)(a, {
                variant: `outline`,
                message: `Recording playback would stream from the mapped recording.`,
                children: `Watch recording`,
              }),
            ],
          }),
        ],
      }),
      (0, d.jsx)(`div`, {
        className: `mt-4`,
        children: (0, d.jsx)(t, {
          state: `Integration Unavailable`,
          children: `Calendar / Meet association and recording mapping are managed by the LMS; no Google connection exists in this prototype.`,
        }),
      }),
    ],
  });
}
export { f as component };
