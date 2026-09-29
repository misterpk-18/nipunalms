import { c as e, f as t, x as n } from "./ui-BRNtr3Vo.js";
import { n as r, r as i, t as a } from "./Certificates-Cz4R92Kq.js";
import { u as o, x as s } from "./index-BqZ61Way.js";
var c = n();
function l() {
  let n = s();
  return (0, c.jsxs)(`div`, {
    className: `mx-auto max-w-6xl space-y-4`,
    children: [
      (0, c.jsx)(e, { title: n(`certificates`), source: `LMS Certificate Register (sample)` }),
      (0, c.jsx)(a, {}),
      (0, c.jsx)(`h2`, { className: `text-lg font-semibold`, children: `My certificates` }),
      (0, c.jsx)(r, { rows: o.filter((e) => e.holder.includes(`Anvitha`)) }),
      (0, c.jsx)(t, {
        state: `Pending Verification`,
        children: `NIT-CRS-052 (complimentary): Configuration Pending — completion rule not configured for this promotional offer.`,
      }),
      (0, c.jsx)(`h2`, { className: `text-lg font-semibold`, children: `Example register entries (reissue / version history)` }),
      (0, c.jsx)(r, { rows: o.filter((e) => !e.holder.includes(`Anvitha`)) }),
      (0, c.jsx)(i, {}),
    ],
  });
}
export { l as component };
