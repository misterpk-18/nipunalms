import { b as e, c as t, i as n, n as r, r as i, s as a, t as o, u as s, x as c } from "./ui-BRNtr3Vo.js";
import { _ as l, x as u } from "./index-BqZ61Way.js";
var d = c();
function f() {
  let c = u(),
    { lang: f, setLang: p } = e();
  return (0, d.jsxs)(`div`, {
    className: `mx-auto max-w-4xl space-y-4`,
    children: [
      (0, d.jsx)(t, { title: c(`profile`) }),
      (0, d.jsx)(n, {
        title: `Identity`,
        children: (0, d.jsx)(a, {
          items: [
            [`Student Master ID`, l.masterId],
            [`Name`, f === `te` ? l.nameTe : l.name],
            [`Email`, l.email],
            [`Mobile`, l.mobile],
            [`Original / admitting branch`, l.originalBranch],
            [`Current service branch`, l.serviceBranch],
            [`Activation`, (0, d.jsx)(r, { children: l.activation }, `a`)],
          ],
        }),
      }),
      (0, d.jsx)(n, {
        title: c(`language`),
        children: (0, d.jsxs)(`div`, {
          className: `flex gap-2`,
          children: [
            (0, d.jsx)(i, { variant: f === `en` ? `primary` : `outline`, onClick: () => p(`en`), children: `English` }),
            (0, d.jsx)(i, {
              variant: f === `te` ? `primary` : `outline`,
              onClick: () => p(`te`),
              children: (0, d.jsx)(`span`, { lang: `te`, children: `తెలుగు` }),
            }),
          ],
        }),
      }),
      (0, d.jsx)(n, {
        title: `Devices & sessions`,
        children: (0, d.jsxs)(`ul`, {
          className: `space-y-2 text-sm`,
          children: [
            (0, d.jsxs)(`li`, {
              className: `flex flex-wrap justify-between gap-2`,
              children: [(0, d.jsx)(`span`, { children: `Chrome · Android — this device` }), (0, d.jsx)(r, { children: `Active` })],
            }),
            (0, d.jsxs)(`li`, {
              className: `flex flex-wrap justify-between gap-2`,
              children: [
                (0, d.jsx)(`span`, { children: `Edge · Windows — 20 Sep 2026` }),
                (0, d.jsx)(s, { variant: `outline`, message: `Session sign-out would be enforced server-side.`, children: `Sign out` }),
              ],
            }),
          ],
        }),
      }),
      (0, d.jsxs)(n, {
        title: `Password & recovery`,
        children: [
          (0, d.jsx)(a, {
            items: [
              [`Password`, `Set by you · last changed 12 Jan 2026`],
              [`Recovery email`, `Verified (sample)`],
              [`MFA`, l.mfa],
            ],
          }),
          (0, d.jsx)(`div`, {
            className: `mt-3`,
            children: (0, d.jsx)(s, { message: `Password change requires your current password.`, children: `Change password` }),
          }),
          (0, d.jsx)(`div`, { className: `mt-3`, children: (0, d.jsx)(o, { children: `Staff cannot view or set your password.` }) }),
        ],
      }),
    ],
  });
}
export { f as component };
