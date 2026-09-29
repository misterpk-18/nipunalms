import { d as e, i as t, o as n, t as r, x as i } from "./ui-BRNtr3Vo.js";
import { t as a } from "./link-IIfPRlSn.js";
import { h as o, l as s } from "./index-BqZ61Way.js";
import { n as c, r as l, t as u } from "./staff-zeGrIO0v.js";
var d = i(),
  f = () => {
    let i = l(),
      f = s.filter((e) => c(i, e.branch));
    return (0, d.jsxs)(u, {
      title: `Branch academic dashboard`,
      source: `LMS academic domain (Module 25 ordering)`,
      children: [
        (0, d.jsxs)(n, {
          cols: 3,
          children: [
            (0, d.jsx)(e, {
              rank: 1,
              label: `Branch verified collections against target`,
              value: `Unavailable`,
              hint: `Not Configured — CRM-authoritative; source not connected`,
            }),
            (0, d.jsx)(e, {
              rank: 2,
              label: `Branch new paid Admissions`,
              value: `Unavailable`,
              hint: `Not Configured — CRM-authoritative; source not connected`,
            }),
            (0, d.jsx)(e, {
              rank: 3,
              label: `Overdue branch follow-ups`,
              value: `Unavailable`,
              hint: `Not Configured — CRM-authoritative; source not connected`,
            }),
          ],
        }),
        (0, d.jsxs)(`div`, {
          className: `grid gap-3 sm:grid-cols-3`,
          "aria-label": `Additional academic widgets`,
          children: [
            (0, d.jsx)(e, { label: `Running / starting batches`, value: f.length }),
            (0, d.jsx)(e, { label: `Schedule & recording exceptions`, value: o.filter((e) => c(i, e.batch)).length }),
            (0, d.jsx)(e, { label: `Open escalations & extension requests`, value: i === `Vijayawada` ? 2 : 3 }),
          ],
        }),
        (0, d.jsx)(t, {
          title: `Go to`,
          children: (0, d.jsxs)(`div`, {
            className: `flex flex-wrap gap-2 text-sm`,
            children: [
              (0, d.jsx)(a, {
                to: `/branch/operations`,
                className: `tap inline-flex items-center rounded-lg border px-3`,
                children: `Batches, schedule & people`,
              }),
              (0, d.jsx)(a, {
                to: `/branch/requests`,
                className: `tap inline-flex items-center rounded-lg border px-3`,
                children: `Escalations & extensions`,
              }),
              (0, d.jsx)(a, {
                to: `/branch/reports`,
                className: `tap inline-flex items-center rounded-lg border px-3`,
                children: `Certificates & reports`,
              }),
            ],
          }),
        }),
        (0, d.jsx)(r, { children: `Finance and Admissions remain in the CRM. This view shows academic data for the locked branch only.` }),
      ],
    });
  };
export { f as component };
