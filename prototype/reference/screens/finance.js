import { a as e, c as t, f as n, n as r, t as i, x as a } from "./ui-BRNtr3Vo.js";
import { x as o } from "./index-BqZ61Way.js";
var s = a(),
  c = [
    { id: `RCT-GNT-2026-00311`, adm: `ADM-GNT-2026-000214`, amt: `₹ 30,000`, state: `Verified`, date: `05 Jan 2026` },
    { id: `RCT-GNT-2026-00544`, adm: `ADM-GNT-2026-000214`, amt: `₹ 12,000`, state: `Verified`, date: `10 Mar 2026` },
    { id: `RCT-GNT-2026-00902`, adm: `ADM-GNT-2026-000214`, amt: `₹ 10,000`, state: `Pending Verification`, date: `22 Sep 2026` },
    { id: `RCT-GNT-2026-00731`, adm: `ADM-VIJ-2026-000088`, amt: `₹ 20,000`, state: `Verified`, date: `01 Aug 2026` },
  ];
function l() {
  let a = o();
  return (0, s.jsxs)(`div`, {
    className: `mx-auto max-w-5xl space-y-4`,
    children: [
      (0, s.jsx)(t, {
        title: a(`finance`),
        subtitle: `Read-only · permitted summary`,
        source: `CRM (authoritative) via controlled API — simulated`,
      }),
      (0, s.jsxs)(`div`, {
        className: `grid gap-3 sm:grid-cols-3`,
        children: [
          (0, s.jsxs)(`div`, {
            className: `rounded-xl border bg-card p-4`,
            children: [
              (0, s.jsx)(`p`, { className: `text-xs text-muted-foreground`, children: `ADM-GNT-2026-000214 fee` }),
              (0, s.jsx)(`p`, { className: `text-xl font-semibold`, children: `₹ 84,000` }),
            ],
          }),
          (0, s.jsxs)(`div`, {
            className: `rounded-xl border bg-card p-4`,
            children: [
              (0, s.jsx)(`p`, { className: `text-xs text-muted-foreground`, children: `Verified receipts` }),
              (0, s.jsx)(`p`, { className: `text-xl font-semibold`, children: `₹ 42,000` }),
            ],
          }),
          (0, s.jsxs)(`div`, {
            className: `rounded-xl border bg-card p-4`,
            children: [
              (0, s.jsx)(`p`, { className: `text-xs text-muted-foreground`, children: `Dues` }),
              (0, s.jsx)(`p`, { className: `text-xl font-semibold`, children: `₹ 42,000` }),
            ],
          }),
        ],
      }),
      (0, s.jsxs)(n, {
        state: `Pending Verification`,
        children: [
          `₹ 10,000 received 22 Sep is Pending Verification and is `,
          (0, s.jsx)(`strong`, { children: `not` }),
          ` counted as paid.`,
        ],
      }),
      (0, s.jsx)(e, {
        caption: `Receipts`,
        rows: c,
        getKey: (e) => e.id,
        cols: [
          { h: `Receipt`, c: (e) => (0, s.jsx)(`span`, { className: `font-mono text-xs`, children: e.id }) },
          { h: `Admission`, c: (e) => e.adm },
          { h: `Amount`, c: (e) => e.amt },
          { h: `Date`, c: (e) => e.date },
          { h: `State`, c: (e) => (0, s.jsx)(r, { children: e.state }) },
        ],
      }),
      (0, s.jsx)(i, {
        children: `CRM remains authoritative for Admission and finance. The LMS never writes to CRM records. Payment actions are not available here.`,
      }),
    ],
  });
}
export { l as component };
