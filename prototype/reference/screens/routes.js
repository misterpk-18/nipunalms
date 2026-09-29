import { b as e, i as t, t as n, v as r, x as i } from "./ui-BRNtr3Vo.js";
import { t as a } from "./link-IIfPRlSn.js";
import { T as o } from "./index-BqZ61Way.js";
var s = i();
function c() {
  let { setRole: i } = e(),
    c = o();
  return (0, s.jsxs)(`main`, {
    className: `mx-auto max-w-4xl px-4 py-8`,
    children: [
      (0, s.jsx)(`h1`, { className: `text-3xl font-semibold tracking-tight`, children: `Nipuna LMS Vision` }),
      (0, s.jsxs)(`p`, {
        className: `mt-2 text-muted-foreground`,
        children: [
          `Interactive prototype of the frozen LMS requirements. Pick a simulated role to begin, or open the `,
          (0, s.jsx)(a, { className: `text-primary underline`, to: `/login`, children: `student login / activation` }),
          ` screen.`,
        ],
      }),
      (0, s.jsx)(`div`, {
        className: `mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3`,
        children: r.map((e) =>
          (0, s.jsxs)(
            `button`,
            {
              onClick: () => {
                (i(e.id), c({ to: e.home }));
              },
              className: `tap rounded-xl border bg-card p-4 text-left shadow-sm hover:border-primary`,
              children: [
                (0, s.jsx)(`div`, { className: `font-semibold`, children: e.label }),
                (0, s.jsxs)(`div`, { className: `text-sm text-muted-foreground`, children: [`Scope: `, e.branch] }),
              ],
            },
            e.id,
          ),
        ),
      }),
      (0, s.jsx)(t, {
        className: `mt-6`,
        title: `Prototype boundaries`,
        children: (0, s.jsxs)(`ul`, {
          className: `list-disc space-y-1 pl-5 text-sm`,
          children: [
            (0, s.jsx)(`li`, {
              children: `CRM is authoritative for Admission and finance; the LMS shows read-only, permitted summaries only.`,
            }),
            (0, s.jsx)(`li`, {
              children: `LMS owns curriculum, batches, actual Class Sessions, content, assignments, tests, attendance, progress and published results.`,
            }),
            (0, s.jsx)(`li`, {
              children: `Certificates come from one LMS Certificate Register; verified placement outcomes from Placement records.`,
            }),
            (0, s.jsx)(`li`, {
              children: `No database, CRM, Google Workspace, Meet, Drive, HDFC, WhatsApp, email, telephony, production login or AI provider is connected.`,
            }),
          ],
        }),
      }),
      (0, s.jsx)(`div`, {
        className: `mt-4`,
        children: (0, s.jsx)(n, {
          children: `Role switching here is a UAT simulation only. Real permissions must be enforced at server, API, query, file, export, notification and AI layers.`,
        }),
      }),
    ],
  });
}
export { c as component };
