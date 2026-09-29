import { a as e, c as t, i as n, n as r, s as i, t as a, u as o, x as s } from "./ui-BRNtr3Vo.js";
import { x as c } from "./index-BqZ61Way.js";
var l = s(),
  u = [
    {
      id: `1`,
      role: `Junior Data Analyst`,
      company: `Sample Analytics Pvt Ltd`,
      round: `Technical round 2 — 02 Oct`,
      state: `In progress`,
    },
    { id: `2`, role: `ML Intern`, company: `Example AI Labs`, round: `HR round done`, state: `Offer — Confirmation Pending` },
    { id: `3`, role: `BI Developer`, company: `Demo Retail Co.`, round: `Not shortlisted`, state: `Closed` },
  ];
function d() {
  let s = c();
  return (0, l.jsxs)(`div`, {
    className: `mx-auto max-w-6xl space-y-4`,
    children: [
      (0, l.jsx)(t, { title: s(`careerSupport`), source: `Placement records (verified outcomes)` }),
      (0, l.jsx)(`p`, {
        role: `note`,
        className: `rounded-lg border-2 border-warning bg-warning-soft p-3 font-semibold text-warning`,
        children: s(`noGuarantee`),
      }),
      (0, l.jsxs)(`div`, {
        className: `grid gap-4 lg:grid-cols-2`,
        children: [
          (0, l.jsxs)(n, {
            title: `Career Profile`,
            children: [
              (0, l.jsx)(i, {
                items: [
                  [`Opt-in`, (0, l.jsx)(r, { children: `Opted in — 14 Aug 2026` }, `o`)],
                  [`Support period`, `Until 12 Jul 2027`],
                  [`Preferred roles`, `Data Analyst, ML Engineer`],
                  [`Preferred locations`, `Hyderabad, Vijayawada, Remote`],
                  [`Consent for employer referral`, (0, l.jsx)(r, { children: `Active — renewable` }, `c`)],
                  [`Profile completeness`, `70% — add a project link`],
                ],
              }),
              (0, l.jsx)(`div`, {
                className: `mt-3 flex flex-wrap gap-2`,
                children: (0, l.jsx)(o, {
                  variant: `outline`,
                  message: `Consent withdrawal would stop all employer referrals.`,
                  children: `Withdraw consent`,
                }),
              }),
            ],
          }),
          (0, l.jsxs)(n, {
            title: `CV versions`,
            children: [
              (0, l.jsxs)(`ul`, {
                className: `space-y-2 text-sm`,
                children: [
                  (0, l.jsxs)(`li`, {
                    className: `flex justify-between`,
                    children: [(0, l.jsx)(`span`, { children: `CV v3 — Data roles` }), (0, l.jsx)(r, { children: `Reviewed` })],
                  }),
                  (0, l.jsxs)(`li`, {
                    className: `flex justify-between`,
                    children: [(0, l.jsx)(`span`, { children: `CV v2` }), (0, l.jsx)(r, { children: `Superseded` })],
                  }),
                ],
              }),
              (0, l.jsx)(`div`, {
                className: `mt-3`,
                children: (0, l.jsx)(o, { message: `CV upload would be stored in LMS placement records.`, children: `Upload new CV` }),
              }),
            ],
          }),
        ],
      }),
      (0, l.jsx)(n, {
        title: `Approved Job Opportunities`,
        children: (0, l.jsx)(`p`, {
          className: `text-sm`,
          children: `2 verified opportunities match your profile. Referral requires complete profile, current consent, readiness and a verified match.`,
        }),
      }),
      (0, l.jsx)(`h2`, { className: `text-lg font-semibold`, children: `My Applications, interviews & offers` }),
      (0, l.jsx)(e, {
        caption: `Applications`,
        rows: u,
        getKey: (e) => e.id,
        cols: [
          { h: `Role`, c: (e) => e.role },
          { h: `Employer`, c: (e) => e.company },
          { h: `Interview round`, c: (e) => e.round },
          { h: `State`, c: (e) => (0, l.jsx)(r, { children: e.state }) },
        ],
      }),
      (0, l.jsx)(n, {
        title: `Next action`,
        children: (0, l.jsx)(`p`, {
          className: `text-sm`,
          children: `Prepare for Technical round 2 (02 Oct). Joining outcome: not yet recorded.`,
        }),
      }),
      (0, l.jsx)(a, { children: `Verified outcomes (offers, joining) come only from Placement records.` }),
    ],
  });
}
export { d as component };
