import { a as e, c as t, i as n, n as r, t as i, u as a, x as o } from "./ui-BRNtr3Vo.js";
import { g as s, x as c } from "./index-BqZ61Way.js";
var l = o(),
  u = [
    ...s
      .filter((e) => e.state === `Delivered`)
      .map((e) => ({ ...e, course: `NIT-CRS-018 · ` + (e.topicId === `top-join` ? `Track 1` : `Track 2`), expiry: `12 Jan 2027` })),
    { ...s[5], course: `NIT-CRS-007 AWS with DevOps`, recording: `Unavailable`, expiry: `Pending — no Joining Date yet` },
  ];
function d() {
  let o = c();
  return (0, l.jsxs)(`div`, {
    className: `mx-auto max-w-6xl`,
    children: [
      (0, l.jsx)(t, { title: o(`recordings`), source: `LMS recording mapping (simulated)` }),
      (0, l.jsxs)(n, {
        className: `mb-4`,
        title: `Access entitlement`,
        children: [
          (0, l.jsxs)(`ul`, {
            className: `list-disc space-y-1 pl-5 text-sm`,
            children: [
              (0, l.jsxs)(`li`, {
                children: [`Default: `, (0, l.jsx)(`strong`, { children: `one calendar year from your confirmed Joining Date` }), `.`],
              }),
              (0, l.jsxs)(`li`, {
                children: [
                  `You may request `,
                  (0, l.jsx)(`strong`, { children: `one extension to the second anniversary` }),
                  ` of the Joining Date. Repeated requests do not add further years.`,
                ],
              }),
              (0, l.jsx)(`li`, {
                children: `A request after first expiry (but before the second anniversary) restores only the remaining time to the second anniversary.`,
              }),
              (0, l.jsx)(`li`, {
                children: `After the second anniversary, only a Founder/CEO or Super Admin exception can extend access.`,
              }),
              (0, l.jsxs)(`li`, {
                children: [`Before a Joining Date exists, expiry shows as `, (0, l.jsx)(`strong`, { children: `Pending` }), `.`],
              }),
            ],
          }),
          (0, l.jsx)(`div`, {
            className: `mt-3`,
            children: (0, l.jsx)(a, {
              variant: `outline`,
              message: `Extension request to 12 Jan 2028 logged for branch review.`,
              children: `Request second-year extension`,
            }),
          }),
        ],
      }),
      (0, l.jsx)(e, {
        caption: `Recordings`,
        rows: u,
        getKey: (e) => e.id,
        cols: [
          { h: `Course / track`, c: (e) => e.course },
          {
            h: `Session`,
            c: (e) =>
              (0, l.jsxs)(l.Fragment, {
                children: [
                  (0, l.jsx)(`div`, { className: `font-medium`, children: e.title }),
                  (0, l.jsxs)(`div`, { className: `text-xs text-muted-foreground`, children: [e.date, ` · `, e.trainer] }),
                ],
              }),
          },
          { h: `Status`, c: (e) => (0, l.jsx)(r, { children: e.recording }) },
          { h: `Access until`, c: (e) => e.expiry },
          { h: `Download`, c: () => `Streaming only — download not permitted` },
          {
            h: `Action`,
            c: (e) =>
              e.recording === `Released` || e.recording === `Partial`
                ? (0, l.jsx)(a, { message: `Playback with captions and keyboard controls would open here.`, children: o(`watch`) })
                : (0, l.jsx)(`span`, { className: `text-xs text-muted-foreground`, children: `Not playable` }),
          },
        ],
      }),
      (0, l.jsx)(`div`, {
        className: `mt-4`,
        children: (0, l.jsx)(i, {
          children: `Media player placeholder targets captions, keyboard play/pause/seek, and speed control. No Drive or Meet connection exists.`,
        }),
      }),
    ],
  });
}
export { d as component };
