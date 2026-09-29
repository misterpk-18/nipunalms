import { a as e, n as t, u as n, x as r } from "./ui-BRNtr3Vo.js";
import { g as i, p as a } from "./index-BqZ61Way.js";
import { r as o, t as s } from "./staff-zeGrIO0v.js";
var c = r(),
  l = () => {
    let r = o(),
      l = i.filter((e) => !r || e.branch === r);
    return (0, c.jsx)(s, {
      title: `Class sessions`,
      subtitle: `Scheduled vs actual Class Session`,
      source: `LMS schedule`,
      children: (0, c.jsx)(e, {
        caption: `Sessions`,
        rows: l,
        getKey: (e) => e.id,
        cols: [
          { h: `When (IST)`, c: (e) => `${e.date} · ${e.time}` },
          { h: `Session`, c: (e) => e.title },
          { h: `Batch`, c: (e) => (0, c.jsx)(`span`, { className: `font-mono text-xs`, children: e.batch }) },
          { h: `Organizer`, c: (e) => (0, c.jsxs)(`span`, { className: `text-xs`, children: [a[e.branch], ` · Pending Verification`] }) },
          { h: `State`, c: (e) => (0, c.jsx)(t, { children: e.state }) },
          { h: `Recording`, c: (e) => (0, c.jsx)(t, { children: e.recording }) },
          {
            h: `Meet`,
            c: (e) => (e.state === `Scheduled` ? (0, c.jsx)(n, { message: `Start Meet as branch organizer.`, children: `Start` }) : `—`),
          },
        ],
      }),
    });
  };
export { l as component };
