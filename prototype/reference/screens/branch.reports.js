import { f as e, i as t, l as n, o as r, x as i } from "./ui-BRNtr3Vo.js";
import { n as a } from "./Certificates-Cz4R92Kq.js";
import { u as o } from "./index-BqZ61Way.js";
import { r as s, t as c } from "./staff-zeGrIO0v.js";
var l = i(),
  u = () => {
    let i = s(),
      u = i === `Vijayawada` ? `VIJ` : `GNT`;
    return (0, l.jsxs)(c, {
      title: `Branch certificates & reports`,
      children: [
        (0, l.jsx)(a, { rows: i ? o.filter((e) => e.holder.includes(u) || (u === `GNT` && e.holder.includes(`Anvitha`))) : o }),
        (0, l.jsxs)(r, {
          cols: 2,
          children: [
            (0, l.jsx)(t, {
              title: `Curriculum delivered`,
              children: (0, l.jsx)(n, { value: i === `Vijayawada` ? 41 : 58, label: `Branch average` }),
            }),
            (0, l.jsx)(t, {
              title: `Placement outcomes`,
              children: (0, l.jsx)(e, { state: `Integration Unavailable`, children: `Placement records not connected.` }),
            }),
          ],
        }),
      ],
    });
  };
export { u as component };
