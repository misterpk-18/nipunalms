import { a as e, n as t, x as n } from "./ui-BRNtr3Vo.js";
var r = n();
function i({ rows: n, caption: i }) {
  return (0, r.jsx)(e, {
    caption: i,
    rows: n,
    getKey: (e) => e.item,
    cols: [
      {
        h: `Item`,
        c: (e) =>
          (0, r.jsxs)(r.Fragment, {
            children: [
              (0, r.jsx)(`div`, { className: `font-medium`, children: e.item }),
              e.note && (0, r.jsx)(`div`, { className: `text-xs text-muted-foreground`, children: e.note }),
            ],
          }),
      },
      { h: `Requirement`, c: (e) => (0, r.jsx)(t, { tone: e.req === `Requirement Approved` ? `success` : `warning`, children: e.req }) },
      { h: `Configuration`, c: (e) => (0, r.jsx)(t, { children: e.config }) },
      { h: `Operational verification`, c: (e) => (0, r.jsx)(t, { children: e.ops }) },
    ],
  });
}
var a = `Requirement Approved`,
  o = `Configuration Pending`,
  s = `Operational Verification Pending`,
  c = [
    {
      item: `CRM ↔ LMS Admission/enrolment events`,
      req: a,
      config: o,
      ops: s,
      note: `Controlled API/events; no direct DB writes. Connection state: Planned.`,
    },
    {
      item: `Google Calendar / Meet — Guntur`,
      req: a,
      config: o,
      ops: s,
      note: `Organizer label trainer@nipunatechnologies.com — account/licence Pending Verification`,
    },
    {
      item: `Google Calendar / Meet — Vijayawada`,
      req: a,
      config: o,
      ops: s,
      note: `Organizer label contactus@nipunatechnologies.com — Pending Verification`,
    },
    { item: `Google Drive recording mapping`, req: a, config: o, ops: s },
    { item: `HDFC payment references (via CRM)`, req: a, config: o, ops: s, note: `CRM-owned; LMS reads summary only` },
    { item: `WhatsApp / email notifications`, req: a, config: o, ops: s, note: `Connection state: Manual` },
    { item: `AI provider (Ask Nipuna)`, req: a, config: o, ops: s, note: `Needs Founder/CEO monthly rupee ceiling` },
    { item: `Production authentication`, req: a, config: o, ops: s },
  ],
  l = [
    {
      item: `Server/API/query/file/export/notification/AI permission enforcement`,
      req: a,
      config: o,
      ops: s,
      note: `Frontend role switcher is UAT only`,
    },
    { item: `Staff inactivity timeout — 30 minutes`, req: a, config: o, ops: s },
    { item: `Staff maximum session — 12 hours`, req: a, config: o, ops: s },
    { item: `Re-authentication for sensitive actions`, req: a, config: o, ops: s },
    { item: `Routine temporary access — max 7 calendar days`, req: a, config: o, ops: s },
    { item: `Elevated / emergency access — max 4 elapsed hours`, req: a, config: o, ops: s },
    { item: `Student MFA — optional unless configured`, req: a, config: o, ops: s },
    { item: `Audit logging of certificate / access decisions`, req: a, config: o, ops: s },
  ];
export { i as n, l as r, c as t };
