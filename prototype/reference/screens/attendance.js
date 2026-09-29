import { a as e, c as t, n, t as r, x as i } from "./ui-BRNtr3Vo.js";
import { g as a, x as o } from "./index-BqZ61Way.js";
var s = i();
function c() {
  let i = o();
  return (0, s.jsxs)(`div`, {
    className: `mx-auto max-w-5xl`,
    children: [
      (0, s.jsx)(t, { title: i(`attendance`), subtitle: `Per actual Class Session`, source: `Trainer-confirmed attendance (LMS)` }),
      (0, s.jsx)(e, {
        caption: `Attendance`,
        rows: a.filter((e) => e.branch === `Guntur`),
        getKey: (e) => e.id,
        cols: [
          { h: `Date`, c: (e) => e.date },
          { h: `Session`, c: (e) => e.title },
          { h: `Trainer`, c: (e) => e.trainer },
          { h: `State`, c: (e) => (0, s.jsx)(n, { children: e.attendance }) },
        ],
      }),
      (0, s.jsx)(`div`, {
        className: `mt-4`,
        children: (0, s.jsx)(r, {
          children: `Joining Date = first confirmed regular-class attendance (demo classes excluded): 12 Jan 2026.`,
        }),
      }),
    ],
  });
}
export { c as component };
