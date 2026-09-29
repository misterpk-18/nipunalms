import { d as e, f as t, i as n, n as r, o as i, t as a, x as o } from "./ui-BRNtr3Vo.js";
import { t as s } from "./link-IIfPRlSn.js";
import { t as c } from "./staff-zeGrIO0v.js";
var l = o(),
  u = () =>
    (0, l.jsxs)(c, {
      title: `Founder / CEO overview`,
      source: `LMS academic domain (Module 25 ordering) · sample`,
      children: [
        (0, l.jsxs)(i, {
          cols: 3,
          children: [
            (0, l.jsx)(e, {
              rank: 1,
              label: `Verified collections against target`,
              value: `Unavailable`,
              hint: `Not Configured — CRM-authoritative finance source not connected (sample)`,
            }),
            (0, l.jsx)(e, {
              rank: 2,
              label: `New paid Admissions against target`,
              value: `Unavailable`,
              hint: `Not Configured — CRM-authoritative Admissions not connected (sample)`,
            }),
            (0, l.jsx)(e, {
              rank: 3,
              label: `Overdue amount`,
              value: `Unavailable`,
              hint: `Not Configured — CRM finance source not connected; not shown as zero`,
            }),
          ],
        }),
        (0, l.jsxs)(`div`, {
          className: `grid gap-3 sm:grid-cols-3`,
          "aria-label": `Additional academic widgets`,
          children: [
            (0, l.jsx)(e, { label: `Active enrolments in delivery`, value: `72`, hint: `Guntur 42 · Vijayawada 30` }),
            (0, l.jsx)(e, { label: `Batches at delivery risk`, value: `2`, hint: `Curriculum mapping, organizer verification` }),
            (0, l.jsx)(e, { label: `Certificates awaiting approval`, value: `1` }),
          ],
        }),
        (0, l.jsx)(n, {
          title: `Decisions needing you`,
          children: (0, l.jsxs)(`ul`, {
            className: `space-y-2 text-sm`,
            children: [
              (0, l.jsxs)(`li`, {
                className: `flex flex-wrap justify-between gap-2`,
                children: [
                  (0, l.jsx)(`span`, { children: `Approve monthly AI rupee ceiling (after developer estimate)` }),
                  (0, l.jsx)(r, { children: `Configuration Pending` }),
                ],
              }),
              (0, l.jsxs)(`li`, {
                className: `flex flex-wrap justify-between gap-2`,
                children: [
                  (0, l.jsx)(`span`, { children: `Recording access exception after 2nd anniversary — Sample Learner L` }),
                  (0, l.jsx)(r, { children: `Awaiting Approval` }),
                ],
              }),
            ],
          }),
        }),
        (0, l.jsx)(t, { state: `Integration Unavailable`, children: `Revenue and collections are CRM figures — not shown here.` }),
        (0, l.jsxs)(`div`, {
          className: `flex flex-wrap gap-2 text-sm`,
          children: [
            (0, l.jsx)(s, { to: `/admin`, className: `tap inline-flex items-center rounded-lg border px-3`, children: `Super Admin view` }),
            (0, l.jsx)(s, { to: `/branch`, className: `tap inline-flex items-center rounded-lg border px-3`, children: `Branch views` }),
          ],
        }),
        (0, l.jsx)(a, { children: `Only approved Module 25 ordering is used; unavailable sources display as Not Configured.` }),
      ],
    });
export { u as component };
