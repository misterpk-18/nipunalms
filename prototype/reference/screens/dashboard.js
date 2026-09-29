import { b as e, c as t, d as n, f as r, i, l as a, n as o, o as s, u as c, x as l } from "./ui-BRNtr3Vo.js";
import { t as u } from "./link-IIfPRlSn.js";
import { _ as d, x as f } from "./index-BqZ61Way.js";
var p = l();
function m() {
  let l = f(),
    { lang: m } = e();
  return (0, p.jsxs)(`div`, {
    className: `mx-auto max-w-6xl`,
    children: [
      (0, p.jsx)(t, {
        title: m === `te` ? `నమస్తే, ${d.nameTe}` : `Welcome, ${d.name}`,
        subtitle: `${d.masterId} · Service branch: Guntur`,
        source: `LMS academic records (sample)`,
      }),
      (0, p.jsxs)(s, {
        cols: 3,
        children: [
          (0, p.jsx)(n, {
            rank: 1,
            label: l(`nextClass`),
            value: `Decision trees`,
            hint: `Mon 28 Sep 2026 · 10:00 IST · Live Online · Trainer M. Demo`,
          }),
          (0, p.jsx)(n, {
            rank: 2,
            label: l(`dueWork`),
            value: `1 required assignment`,
            hint: `Regression on housing dataset · due 29 Sep 23:59 IST`,
          }),
          (0, p.jsxs)(`div`, {
            className: `rounded-xl border bg-card p-4 shadow-sm`,
            children: [
              (0, p.jsxs)(`div`, {
                className: `flex items-center gap-2 text-xs font-medium uppercase text-muted-foreground`,
                children: [
                  (0, p.jsx)(`span`, {
                    className: `grid size-5 place-items-center rounded-full bg-navy text-[11px] text-navy-foreground`,
                    children: `3`,
                  }),
                  l(`courseProgress`),
                ],
              }),
              (0, p.jsxs)(`div`, {
                className: `mt-2 space-y-2`,
                children: [
                  (0, p.jsx)(a, { value: 46, label: `Curriculum delivered (NIT-CRS-018)` }),
                  (0, p.jsx)(`p`, {
                    className: `text-xs text-muted-foreground`,
                    children: `Separate from attendance and required learning — see Progress.`,
                  }),
                ],
              }),
            ],
          }),
        ],
      }),
      (0, p.jsx)(`div`, {
        className: `mt-2 flex flex-wrap gap-2`,
        children: (0, p.jsx)(c, {
          message: `Join Class opens Google Meet in production. Meet organizer: trainer@nipunatechnologies.com — Pending Verification.`,
          children: l(`joinClass`),
        }),
      }),
      (0, p.jsxs)(`div`, {
        className: `mt-6 grid gap-4 lg:grid-cols-3`,
        children: [
          (0, p.jsx)(i, {
            title: l(`continueLearning`),
            className: `lg:col-span-2`,
            children: (0, p.jsxs)(`p`, {
              className: `text-sm`,
              children: [
                `Track 2 · Machine Learning → Supervised Learning → `,
                (0, p.jsx)(u, {
                  className: `text-primary underline`,
                  to: `/topics/$topicId`,
                  params: { topicId: `top-reg` },
                  children: `Linear & Logistic Regression`,
                }),
              ],
            }),
          }),
          (0, p.jsxs)(i, {
            title: l(`latestRecording`),
            children: [
              (0, p.jsx)(`p`, { className: `text-sm`, children: `Window functions lab · 02 Sep 2026` }),
              (0, p.jsx)(`div`, { className: `mt-2`, children: (0, p.jsx)(o, { children: `Released` }) }),
              (0, p.jsx)(`p`, {
                className: `mt-1 text-xs text-muted-foreground`,
                children: `Access until 12 Jan 2027 (1 year from Joining Date)`,
              }),
            ],
          }),
          (0, p.jsxs)(i, {
            title: l(`upcomingWork`),
            children: [
              (0, p.jsx)(`p`, { className: `text-sm`, children: `Supervised Learning module test · 03 Oct 2026` }),
              (0, p.jsx)(u, { to: `/tests`, className: `text-sm text-primary underline`, children: l(`viewAll`) }),
            ],
          }),
          (0, p.jsx)(i, {
            title: l(`attendanceAlert`),
            children: (0, p.jsx)(r, {
              state: `Pending Verification`,
              children: `1 absence on 21 Sep has an approved recovery reference (REC-0041).`,
            }),
          }),
          (0, p.jsxs)(i, {
            title: l(`certStatus`),
            children: [
              (0, p.jsx)(o, { children: `Not Yet Eligible` }),
              (0, p.jsx)(`p`, { className: `mt-1 text-xs text-muted-foreground`, children: `From LMS Certificate Register.` }),
            ],
          }),
          (0, p.jsxs)(i, {
            title: l(`careerSupport`),
            children: [
              (0, p.jsx)(`p`, { className: `text-sm`, children: `Opted in · Profile 70% complete` }),
              (0, p.jsx)(`p`, { className: `mt-1 text-xs`, children: l(`noGuarantee`) }),
            ],
          }),
          (0, p.jsx)(i, {
            title: l(`support`),
            children: (0, p.jsx)(`p`, { className: `text-sm`, children: `1 open request · Owner: Academic Coordinator GNT` }),
          }),
          (0, p.jsxs)(i, {
            title: l(`askNipuna`),
            children: [
              (0, p.jsx)(o, { tone: `sim`, children: `AI Available (simulated)` }),
              (0, p.jsx)(`p`, { className: `mt-1 text-xs text-muted-foreground`, children: `12 of 50 daily responses used (IST).` }),
            ],
          }),
        ],
      }),
      (0, p.jsx)(`div`, {
        className: `mt-6`,
        children: (0, p.jsx)(r, {
          state: `Stale`,
          children: `Engagement data last refreshed 6 hours ago (sample). Shown as Stale rather than as zero.`,
        }),
      }),
    ],
  });
}
export { m as component };
