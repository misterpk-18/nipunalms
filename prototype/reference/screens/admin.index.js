import { a as e, d as t, f as n, i as r, n as i, o as a, t as o, x as s } from "./ui-BRNtr3Vo.js";
import { t as c } from "./link-IIfPRlSn.js";
import { t as l } from "./staff-zeGrIO0v.js";
var u = s(),
  d = [
    { id: `1`, flow: `CRM → LMS Admission.created`, last: `Never (not connected)`, s: `Integration Unavailable` },
    { id: `2`, flow: `CRM → LMS Receipt.verified`, last: `Never (not connected)`, s: `Integration Unavailable` },
    { id: `3`, flow: `LMS → CRM Enrolment.status`, last: `Never (not connected)`, s: `Integration Unavailable` },
  ],
  f = [
    {
      id: `P-11`,
      what: `LMS login for NIT-STU-2026-004190`,
      issue: `Duplicate family mobile — identity check required`,
      s: `Pending Verification`,
    },
    { id: `P-12`, what: `Meet association NIT-VIJ-BAT-2026-000001`, issue: `Organizer licence unverified`, s: `Failed` },
  ],
  p = () =>
    (0, u.jsxs)(l, {
      title: `Super Admin — all authorised branches`,
      source: `Readiness register (sample)`,
      children: [
        (0, u.jsxs)(a, {
          cols: 3,
          children: [
            (0, u.jsx)(t, {
              rank: 1,
              label: `Critical integration failures`,
              value: `Not Configured`,
              hint: `No live integrations; monitoring Configuration Pending (sample)`,
            }),
            (0, u.jsx)(t, {
              rank: 2,
              label: `Work awaiting named ownership/cover`,
              value: 3,
              hint: `Sample: curriculum mapping recovery, recording exception, provisioning`,
            }),
            (0, u.jsx)(t, {
              rank: 3,
              label: `Overdue payment verifications`,
              value: `Unavailable`,
              hint: `Not Configured — CRM/finance-authoritative source not connected`,
            }),
          ],
        }),
        (0, u.jsxs)(`div`, {
          className: `grid gap-3 sm:grid-cols-3`,
          "aria-label": `Additional academic widgets`,
          children: [
            (0, u.jsx)(t, { label: `Integrations operationally verified`, value: `0 / 8`, hint: `All Configuration Pending` }),
            (0, u.jsx)(t, { label: `Failed provisioning`, value: f.length }),
            (0, u.jsx)(t, { label: `Open exceptions (all queues)`, value: 9 }),
          ],
        }),
        (0, u.jsx)(n, {
          state: `Integration Unavailable`,
          children: `CRM/LMS sync, Meet, Drive, AI and messaging are not live in this prototype.`,
        }),
        (0, u.jsx)(`h2`, { className: `font-semibold`, children: `CRM / LMS sync status` }),
        (0, u.jsx)(e, {
          caption: `Sync`,
          rows: d,
          getKey: (e) => e.id,
          cols: [
            { h: `Flow`, c: (e) => e.flow },
            { h: `Last successful`, c: (e) => e.last },
            { h: `State`, c: (e) => (0, u.jsx)(i, { children: e.s }) },
          ],
        }),
        (0, u.jsx)(`h2`, { className: `font-semibold`, children: `Provisioning exceptions` }),
        (0, u.jsx)(e, {
          caption: `Provisioning`,
          rows: f,
          getKey: (e) => e.id,
          cols: [
            { h: `ID`, c: (e) => e.id },
            { h: `Item`, c: (e) => e.what },
            { h: `Issue`, c: (e) => e.issue },
            { h: `State`, c: (e) => (0, u.jsx)(i, { children: e.s }) },
          ],
        }),
        (0, u.jsx)(r, {
          title: `AI status`,
          children: (0, u.jsxs)(`p`, {
            className: `text-sm`,
            children: [
              `Ask Nipuna: `,
              (0, u.jsx)(i, { children: `Configuration Pending` }),
              ` · Student 50 / Staff 100 responses per IST day · monthly rupee ceiling not yet approved.`,
            ],
          }),
        }),
        (0, u.jsx)(r, {
          title: `Go to`,
          children: (0, u.jsxs)(`div`, {
            className: `flex flex-wrap gap-2 text-sm`,
            children: [
              (0, u.jsx)(c, {
                to: `/admin/integrations`,
                className: `tap inline-flex items-center rounded-lg border px-3`,
                children: `Integration readiness`,
              }),
              (0, u.jsx)(c, {
                to: `/admin/exceptions`,
                className: `tap inline-flex items-center rounded-lg border px-3`,
                children: `Exception queues`,
              }),
              (0, u.jsx)(c, {
                to: `/admin/security`,
                className: `tap inline-flex items-center rounded-lg border px-3`,
                children: `Security readiness`,
              }),
              (0, u.jsx)(c, {
                to: `/academic`,
                className: `tap inline-flex items-center rounded-lg border px-3`,
                children: `Academic (all branches)`,
              }),
              (0, u.jsx)(c, { to: `/branch`, className: `tap inline-flex items-center rounded-lg border px-3`, children: `Branch views` }),
            ],
          }),
        }),
        (0, u.jsx)(o, {
          children: `Readiness views only — no live administration. Server/API permissions remain production Pending Verification.`,
        }),
      ],
    });
export { p as component };
