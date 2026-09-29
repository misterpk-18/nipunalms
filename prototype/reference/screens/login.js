import { S as e, b as t, f as n, i as r, n as i, r as a, t as o, u as s, w as c, x as l } from "./ui-BRNtr3Vo.js";
import { T as u, x as d } from "./index-BqZ61Way.js";
var f = c(e()),
  p = l(),
  m = [
    [`Account Created`, `ఖాతా సృష్టించబడింది`],
    [`Activation Pending`, `యాక్టివేషన్ పెండింగ్`],
    [`Activated`, `యాక్టివేట్ అయింది`],
    [`Course Access Released`, `కోర్సు యాక్సెస్ విడుదలైంది`],
  ];
function h() {
  let e = d(),
    { lang: c, setRole: l } = t(),
    h = u(),
    [g, _] = (0, f.useState)(``),
    [v, y] = (0, f.useState)(``),
    [b, x] = (0, f.useState)(null),
    [S, C] = (0, f.useState)(2),
    w = c === `te`;
  return (0, p.jsxs)(`main`, {
    className: `mx-auto grid max-w-5xl gap-6 px-4 py-6 lg:grid-cols-2`,
    children: [
      (0, p.jsxs)(r, {
        title: e(`login`),
        children: [
          (0, p.jsxs)(`form`, {
            noValidate: !0,
            onSubmit: (t) => {
              if ((t.preventDefault(), !g || !v)) {
                x(e(`requiredField`));
                return;
              }
              (x(null), l(`student`), h({ to: `/dashboard` }));
            },
            className: `space-y-4`,
            children: [
              (0, p.jsxs)(`div`, {
                children: [
                  (0, p.jsx)(`label`, { htmlFor: `lid`, className: `mb-1 block text-sm font-medium`, children: e(`loginId`) }),
                  (0, p.jsx)(`input`, {
                    id: `lid`,
                    value: g,
                    onChange: (e) => _(e.target.value),
                    "aria-invalid": !!b && !g,
                    "aria-describedby": b ? `lerr` : void 0,
                    placeholder: `NIT-STU-2026-004182 / anvitha.sample@example.test`,
                    className: `tap w-full rounded-lg border border-input bg-card px-3`,
                  }),
                ],
              }),
              (0, p.jsxs)(`div`, {
                children: [
                  (0, p.jsx)(`label`, { htmlFor: `lpw`, className: `mb-1 block text-sm font-medium`, children: e(`password`) }),
                  (0, p.jsx)(`input`, {
                    id: `lpw`,
                    type: `password`,
                    value: v,
                    onChange: (e) => y(e.target.value),
                    "aria-invalid": !!b && !v,
                    className: `tap w-full rounded-lg border border-input bg-card px-3`,
                  }),
                ],
              }),
              b && (0, p.jsxs)(`p`, { id: `lerr`, role: `alert`, className: `text-sm font-medium text-danger`, children: [`⚠ `, b] }),
              (0, p.jsxs)(a, { type: `submit`, className: `w-full`, children: [e(`login`), ` (prototype)`] }),
              (0, p.jsx)(`p`, {
                className: `text-xs text-muted-foreground`,
                children: w
                  ? `ప్రోటోటైప్: ఏ విలువైనా సైన్ ఇన్ అవుతుంది; నిజమైన ప్రామాణీకరణ లేదు.`
                  : `Prototype: any non-empty value signs in; no real authentication.`,
              }),
            ],
          }),
          (0, p.jsxs)(`div`, {
            className: `mt-4 flex flex-wrap gap-2`,
            children: [
              (0, p.jsx)(s, {
                variant: `outline`,
                message: w ? `పాస్‌వర్డ్ రీసెట్ లింక్.` : `Password reset link to registered email/mobile.`,
                children: e(`forgot`),
              }),
              (0, p.jsx)(s, {
                variant: `outline`,
                message: `Assisted identity verification request raised to branch support (identity checked against Student Master, not shared family mobile).`,
                children: w ? `సహాయంతో గుర్తింపు ధృవీకరణ` : `Assisted identity verification`,
              }),
            ],
          }),
          (0, p.jsx)(`div`, {
            className: `mt-4`,
            children: (0, p.jsx)(o, {
              children: w
                ? `సిబ్బంది మీ పాస్‌వర్డ్‌ను చూడలేరు లేదా సెట్ చేయలేరు. రీసెట్ మీరు మాత్రమే పూర్తి చేస్తారు.`
                : `Staff can never see or set your password. Resets are completed only by you through a verified link.`,
            }),
          }),
        ],
      }),
      (0, p.jsxs)(`div`, {
        className: `space-y-4`,
        children: [
          (0, p.jsxs)(r, {
            title: w ? `ఖాతా యాక్టివేషన్ స్థితి` : `Account activation status`,
            children: [
              (0, p.jsx)(`ol`, {
                className: `space-y-3`,
                children: m.map(([e, t], n) =>
                  (0, p.jsxs)(
                    `li`,
                    {
                      className: `flex items-center gap-3`,
                      children: [
                        (0, p.jsx)(`span`, {
                          className: `grid size-7 place-items-center rounded-full text-xs font-bold ${n <= S ? `bg-primary text-primary-foreground` : `bg-muted text-muted-foreground`}`,
                          children: n + 1,
                        }),
                        (0, p.jsx)(`span`, { className: `flex-1`, children: w ? t : e }),
                        (0, p.jsx)(i, {
                          tone: n < S ? `success` : n === S ? `info` : `neutral`,
                          children: n < S ? `Done` : n === S ? `Current` : `Not yet`,
                        }),
                      ],
                    },
                    e,
                  ),
                ),
              }),
              (0, p.jsx)(`div`, {
                className: `mt-3 flex flex-wrap gap-2`,
                children: m.map((e, t) =>
                  (0, p.jsxs)(a, { variant: `outline`, className: `text-xs`, onClick: () => C(t), children: [`Preview: `, e[0]] }, e[0]),
                ),
              }),
              S < 3 &&
                (0, p.jsx)(`div`, {
                  className: `mt-3`,
                  children: (0, p.jsx)(n, {
                    state: `Confirmation Pending`,
                    children: w
                      ? `బ్యాచ్ కేటాయింపు తర్వాత కోర్సు యాక్సెస్ విడుదల అవుతుంది.`
                      : `Course access is released after academic batch allocation.`,
                  }),
                }),
            ],
          }),
          (0, p.jsxs)(r, {
            title: w ? `పరికరం & సెషన్ సమాచారం` : `Device & session information`,
            children: [
              (0, p.jsx)(`p`, {
                className: `text-sm`,
                children: w
                  ? `ఈ పరికరం: Chrome · Android (నమూనా). చివరి సైన్-ఇన్: 25 సెప్టెం 2026, 19:02 IST.`
                  : `This device: Chrome · Android (sample). Last sign-in: 25 Sep 2026, 19:02 IST.`,
              }),
              (0, p.jsx)(`p`, {
                className: `mt-1 text-xs text-muted-foreground`,
                children: w
                  ? `విద్యార్థులకు CRM లాగిన్ లేదు. ఒక వ్యక్తికి ఒకే LMS లాగిన్.`
                  : `Students have no CRM login. One LMS login per person across branches.`,
              }),
            ],
          }),
        ],
      }),
    ],
  });
}
export { h as component };
