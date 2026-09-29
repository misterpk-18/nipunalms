import { b as e, c as t, x as n } from "./ui-BRNtr3Vo.js";
var r = n();
function i() {
  let { role: t } = e();
  return t.branch === `All authorised branches` ? null : t.branch;
}
function a(e, t) {
  return !e || t.includes(e) || t.includes(e === `Guntur` ? `GNT` : `VIJ`);
}
function o({ title: n, subtitle: i, source: a, children: o, actions: s }) {
  let { role: c } = e();
  return (0, r.jsxs)(`div`, {
    className: `mx-auto max-w-6xl space-y-4`,
    children: [(0, r.jsx)(t, { title: n, subtitle: `${i ? i + ` · ` : ``}${c.label} · scope: ${c.branch}`, source: a, children: s }), o],
  });
}
export { a as n, i as r, o as t };
