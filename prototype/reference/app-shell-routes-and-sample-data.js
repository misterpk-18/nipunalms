    [`path`, { d: `M18 6 6 18`, key: `1bl5f8` }],
    [`path`, { d: `m6 6 12 12`, key: `d8bk6v` }],
  ]),
  Fl = {
    home: [`Home`, `హోమ్`],
    myLearning: [`My Learning`, `నా అభ్యాసం`],
    myCourses: [`My Courses`, `నా కోర్సులు`],
    schedule: [`Schedule`, `షెడ్యూల్`],
    tasks: [`Tasks`, `పనులు`],
    more: [`More`, `మరిన్ని`],
    recordings: [`Recordings`, `రికార్డింగ్‌లు`],
    resources: [`Resources`, `వనరులు`],
    assignments: [`Assignments`, `అసైన్‌మెంట్‌లు`],
    tests: [`Tests`, `పరీక్షలు`],
    attendance: [`Attendance`, `హాజరు`],
    progress: [`Progress`, `పురోగతి`],
    results: [`Results`, `ఫలితాలు`],
    certificates: [`Certificates`, `సర్టిఫికెట్లు`],
    career: [`Career`, `కెరీర్`],
    askNipuna: [`Ask Nipuna`, `నిపుణను అడగండి`],
    support: [`Support`, `సహాయం`],
    notifications: [`Notifications`, `నోటిఫికేషన్లు`],
    finance: [`Fees & Receipts`, `ఫీజులు & రసీదులు`],
    profile: [`Profile`, `ప్రొఫైల్`],
    nextClass: [`Next Class`, `తదుపరి తరగతి`],
    dueWork: [`Due Work`, `గడువు పనులు`],
    courseProgress: [`Current Course Progress`, `ప్రస్తుత కోర్సు పురోగతి`],
    continueLearning: [`Continue Learning`, `అభ్యాసం కొనసాగించండి`],
    latestRecording: [`Latest Released Recording`, `తాజా విడుదలైన రికార్డింగ్`],
    upcomingWork: [`Upcoming Assignment / Test`, `రాబోయే అసైన్‌మెంట్ / పరీక్ష`],
    attendanceAlert: [`Attendance Alert`, `హాజరు హెచ్చరిక`],
    certStatus: [`Certificate Status`, `సర్టిఫికెట్ స్థితి`],
    careerSupport: [`Career Support`, `కెరీర్ సహాయం`],
    joinClass: [`Join Class`, `తరగతిలో చేరండి`],
    watch: [`Watch`, `చూడండి`],
    submit: [`Submit`, `సమర్పించండి`],
    login: [`Sign in`, `సైన్ ఇన్`],
    loginId: [`Student ID or email`, `విద్యార్థి ID లేదా ఇమెయిల్`],
    password: [`Password`, `పాస్‌వర్డ్`],
    forgot: [`Forgot password?`, `పాస్‌వర్డ్ మర్చిపోయారా?`],
    requiredField: [`This field is required.`, `ఈ ఫీల్డ్ తప్పనిసరి.`],
    demoOnly: [`Demo only — no live service is connected.`, `డెమో మాత్రమే — ఏ లైవ్ సేవ కనెక్ట్ కాలేదు.`],
    pendingVerification: [`Pending Verification`, `ధృవీకరణ పెండింగ్‌లో ఉంది`],
    notConfigured: [`Not Configured`, `కాన్ఫిగర్ చేయలేదు`],
    viewAll: [`View all`, `అన్నీ చూడండి`],
    raiseRequest: [`Raise a request`, `అభ్యర్థన చేయండి`],
    language: [`Language`, `భాష`],
    noGuarantee: [
      `Placement / career assistance only — no guaranteed placement.`,
      `ప్లేస్‌మెంట్ / కెరీర్ సహాయం మాత్రమే — ఉద్యోగ హామీ లేదు.`,
    ],
  };
function Il(e, t) {
  return Fl[t][e === `en` ? 0 : 1];
}
function Ll() {
  let { lang: e } = r();
  return (t) => Il(e, t);
}
var Rl = [
    { to: `/dashboard`, label: `Home`, tkey: `home`, icon: Sl },
    { to: `/my-courses`, label: `My Learning`, tkey: `myLearning`, icon: H },
    { to: `/schedule`, label: `Schedule`, tkey: `schedule`, icon: ml },
    { to: `/assignments`, label: `Tasks`, tkey: `tasks`, icon: Tl },
    { to: `/recordings`, label: `Recordings`, tkey: `recordings`, icon: Ml },
    { to: `/resources`, label: `Resources`, tkey: `resources`, icon: yl },
    { to: `/tests`, label: `Tests`, tkey: `tests`, icon: vl },
    { to: `/attendance`, label: `Attendance`, tkey: `attendance`, icon: kl },
    { to: `/progress`, label: `Progress`, tkey: `progress`, icon: hl },
    { to: `/results`, label: `Results`, tkey: `results`, icon: gl },
    { to: `/certificates`, label: `Certificates`, tkey: `certificates`, icon: ll },
    { to: `/career`, label: `Career`, tkey: `career`, icon: fl },
    { to: `/ask-nipuna`, label: `Ask Nipuna`, tkey: `askNipuna`, icon: Ol },
    { to: `/support`, label: `Support`, tkey: `support`, icon: wl },
    { to: `/notifications`, label: `Notifications`, tkey: `notifications`, icon: ul },
    { to: `/finance`, label: `Fees & Receipts`, tkey: `finance`, icon: Nl },
    { to: `/profile`, label: `Profile`, tkey: `profile`, icon: Al },
  ],
  zl = [`/dashboard`, `/my-courses`, `/schedule`, `/assignments`],
  Bl = [
    { to: `/trainer`, label: `Today`, icon: Sl },
    { to: `/trainer/batches`, label: `Batches`, icon: Cl },
    { to: `/trainer/students`, label: `Students`, icon: jl },
    { to: `/trainer/reviews`, label: `Reviews`, icon: gl },
    { to: `/trainer/sessions`, label: `Sessions`, icon: ml },
    { to: `/trainer/attendance`, label: `Attendance`, icon: kl },
    { to: `/trainer/content`, label: `Content`, icon: yl },
    { to: `/trainer/assignments`, label: `Assignments`, icon: Tl },
    { to: `/trainer/assessments`, label: `Assessments`, icon: vl },
    { to: `/trainer/support`, label: `Support`, icon: wl },
    { to: `/trainer/notifications`, label: `Notifications`, icon: ul },
    { to: `/trainer/reports`, label: `Reports`, icon: hl },
    { to: `/trainer/ask-nipuna`, label: `Ask Nipuna`, icon: Ol },
  ],
  Vl = [`/trainer`, `/trainer/batches`, `/trainer/students`, `/trainer/reviews`],
  Hl = [
    { to: `/academic`, label: `Dashboard`, icon: Sl },
    { to: `/academic/batches`, label: `Batches`, icon: Cl },
    { to: `/academic/assessments`, label: `Reviews`, icon: gl },
    { to: `/academic/exceptions`, label: `Exceptions`, icon: El },
    { to: `/academic/curriculum`, label: `Curriculum`, icon: dl },
    { to: `/academic/schedule`, label: `Schedule`, icon: ml },
    { to: `/academic/content-review`, label: `Content Review`, icon: yl },
    { to: `/academic/recording-exceptions`, label: `Recording Exceptions`, icon: Ml },
    { to: `/academic/progress`, label: `Attendance & Progress`, icon: hl },
    { to: `/academic/completion`, label: `Completion Review`, icon: xl },
    { to: `/academic/certificates`, label: `Certificate Eligibility`, icon: ll },
    { to: `/academic/support`, label: `Academic Support`, icon: wl },
    { to: `/academic/reports`, label: `Reports`, icon: hl },
  ],
  U = [`/academic`, `/academic/batches`, `/academic/assessments`, `/academic/exceptions`],
  W = [
    { to: `/branch`, label: `Branch Dashboard`, icon: pl },
    { to: `/branch/operations`, label: `Batches, Schedule & People`, icon: Cl },
    { to: `/branch/requests`, label: `Escalations & Extensions`, icon: wl },
    { to: `/branch/reports`, label: `Certificates & Reports`, icon: ll },
  ],
  G = [
    { to: `/admin`, label: `Super Admin`, icon: bl },
    { to: `/admin/integrations`, label: `Integration Readiness`, icon: Cl },
    { to: `/admin/exceptions`, label: `Exception Queues`, icon: El },
    { to: `/admin/security`, label: `Security Readiness`, icon: Dl },
    { to: `/academic`, label: `Academic (all branches)`, icon: xl },
    { to: `/branch`, label: `Branch views`, icon: pl },
  ],
  K = [
    { to: `/founder`, label: `Founder Dashboard`, icon: bl },
    { to: `/admin`, label: `Super Admin view`, icon: Dl },
    { to: `/branch`, label: `Branch views`, icon: pl },
  ];
function q(e) {
  return e === `/` || e.startsWith(`/login`)
    ? null
    : e.startsWith(`/trainer`)
      ? `trainer`
      : e.startsWith(`/academic`)
        ? `academic`
        : e.startsWith(`/branch`)
          ? `branch`
          : e.startsWith(`/admin`)
            ? `admin`
            : e.startsWith(`/founder`)
              ? `founder`
              : `student`;
}
function Ul() {
  return (0, L.jsx)(`div`, {
    role: `note`,
    className: `sticky top-0 z-50 bg-banner px-3 py-1.5 text-center text-xs font-bold tracking-wide text-banner-foreground`,
    children: `NIPUNA LMS — INTERACTIVE PROTOTYPE — SAMPLE DATA — NO LIVE INTEGRATIONS`,
  });
}
function Wl() {
  let { role: e, setRole: t } = r(),
    n = bs();
  return (0, L.jsxs)(`label`, {
    className: `flex min-w-0 items-center gap-2 rounded-lg border border-dashed border-sim/60 bg-sim-soft px-2 py-1 text-sim`,
    children: [
      (0, L.jsx)(o, { className: `size-4 shrink-0`, "aria-hidden": !0 }),
      (0, L.jsx)(`span`, { className: `hidden text-[11px] font-bold uppercase sm:inline`, children: `UAT role (sample)` }),
      (0, L.jsx)(`select`, {
        "aria-label": `Prototype UAT role simulator — sample only, not a security boundary`,
        value: e.id,
        onChange: (e) => {
          let r = c.find((t) => t.id === e.target.value);
          (t(r.id), n({ to: r.home }));
        },
        className: `tap min-w-0 max-w-[11rem] rounded bg-card px-1 text-xs font-medium text-foreground sm:max-w-none`,
        children: c.map((e) => (0, L.jsx)(`option`, { value: e.id, children: e.label }, e.id)),
      }),
    ],
  });
}
function Gl() {
  let { lang: e, setLang: t } = r();
  return (0, L.jsxs)(`div`, {
    role: `group`,
    "aria-label": `Language / భాష`,
    className: `flex overflow-hidden rounded-lg border`,
    children: [
      (0, L.jsx)(`button`, {
        onClick: () => t(`en`),
        "aria-pressed": e === `en`,
        className: s(`tap px-2 text-xs font-medium`, e === `en` ? `bg-primary text-primary-foreground` : `bg-card text-foreground`),
        children: `EN`,
      }),
      (0, L.jsx)(`button`, {
        lang: `te`,
        onClick: () => t(`te`),
        "aria-pressed": e === `te`,
        className: s(`tap px-2 text-xs font-medium`, e === `te` ? `bg-primary text-primary-foreground` : `bg-card text-foreground`),
        children: `తెలుగు`,
      }),
    ],
  });
}
function Kl() {
  let { toasts: e } = r();
  return (0, L.jsx)(`div`, {
    "aria-live": `polite`,
    className: `fixed inset-x-3 bottom-20 z-[60] flex flex-col items-center gap-2 md:bottom-4 md:left-auto md:right-4 md:items-end`,
    children: e.map((e) =>
      (0, L.jsxs)(
        `div`,
        {
          className: `max-w-md rounded-lg border border-sim/40 bg-card px-4 py-3 text-sm shadow-lg`,
          children: [(0, L.jsx)(o, { className: `mr-1 inline size-4 text-sim`, "aria-hidden": !0 }), e.text],
        },
        e.id,
      ),
    ),
  });
}
function ql({ children: e }) {
  let t = qs({ select: (e) => e.location.pathname }),
    { role: n } = r(),
    a = Ll(),
    [o, c] = (0, I.useState)(!1),
    l = q(t);
  if (!l)
    return (0, L.jsxs)(L.Fragment, {
      children: [
        (0, L.jsx)(Ul, {}),
        (0, L.jsxs)(`div`, { className: `flex justify-end gap-2 p-2`, children: [(0, L.jsx)(Gl, {}), (0, L.jsx)(Wl, {})] }),
        e,
        (0, L.jsx)(Kl, {}),
      ],
    });
  let u = { student: Rl, trainer: Bl, academic: Hl, branch: W, admin: G, founder: K }[n.workspace],
    f = { student: zl, trainer: Vl, academic: U }[n.workspace] ?? u.slice(0, 4).map((e) => e.to),
    p = (e) => (n.workspace === `student` && e.tkey ? a(e.tkey) : e.label),
    m = d(n, l),
    h = (e) => t === e || (e !== `/trainer` && e !== `/academic` && e !== `/branch` && e !== `/admin` && t.startsWith(e + `/`));
  return (0, L.jsxs)(`div`, {
    className: `min-h-screen`,
    children: [
      (0, L.jsx)(Ul, {}),
      (0, L.jsx)(`header`, {
        className: `sticky top-[30px] z-40 border-b bg-navy text-navy-foreground`,
        children: (0, L.jsxs)(`div`, {
          className: `flex items-center gap-2 px-3 py-2 sm:px-5`,
          children: [
            (0, L.jsxs)(ve, {
              to: n.home,
              className: `flex shrink-0 items-center gap-2 font-semibold`,
              children: [
                (0, L.jsx)(`span`, {
                  className: `grid size-8 place-items-center rounded-lg bg-primary text-primary-foreground`,
                  children: (0, L.jsx)(xl, { className: `size-5`, "aria-hidden": !0 }),
                }),
                (0, L.jsx)(`span`, { className: `hidden sm:inline`, children: `Nipuna LMS` }),
              ],
            }),
            (0, L.jsxs)(`span`, {
              className: `hidden truncate rounded bg-navy-muted px-2 py-0.5 text-xs lg:inline`,
              children: [n.label, ` · `, n.branch],
            }),
            (0, L.jsxs)(`div`, {
              className: `ml-auto flex min-w-0 items-center gap-2`,
              children: [n.workspace === `student` && (0, L.jsx)(Gl, {}), (0, L.jsx)(Wl, {})],
            }),
          ],
        }),
      }),
      (0, L.jsxs)(`div`, {
        className: `flex`,
        children: [
          (0, L.jsxs)(`nav`, {
            "aria-label": `Main`,
            className: `sticky top-[86px] hidden h-[calc(100vh-86px)] w-60 shrink-0 overflow-y-auto border-r bg-card p-3 md:block`,
            children: [
              (0, L.jsx)(`ul`, {
                className: `space-y-0.5`,
                children: u.map((e) =>
                  (0, L.jsx)(
                    `li`,
                    {
                      children: (0, L.jsxs)(ve, {
                        to: e.to,
                        className: s(
                          `tap flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm`,
                          h(e.to) ? `bg-accent font-semibold text-accent-foreground` : `text-foreground hover:bg-muted`,
                        ),
                        children: [(0, L.jsx)(e.icon, { className: `size-4 shrink-0`, "aria-hidden": !0 }), p(e)],
                      }),
                    },
                    e.to,
                  ),
                ),
              }),
              (0, L.jsx)(`p`, {
                className: `mt-4 rounded-lg bg-sim-soft p-2 text-[11px] text-sim`,
                children: `Role switcher is a prototype UAT aid only — not a production security boundary.`,
              }),
            ],
          }),
          (0, L.jsx)(`main`, {
            id: `main`,
            className: `min-w-0 flex-1 px-3 pb-28 pt-4 sm:px-6 md:pb-10`,
            children: m
              ? e
              : (0, L.jsx)(`div`, {
                  className: `mx-auto max-w-lg py-10`,
                  children: (0, L.jsxs)(i, {
                    state: `Permission Restricted`,
                    children: [
                      `The current simulated role (`,
                      n.label,
                      `) cannot open this workspace. `,
                      (0, L.jsx)(ve, { className: `underline`, to: n.home, children: `Go to your home` }),
                      `.`,
                    ],
                  }),
                }),
          }),
        ],
      }),
      (0, L.jsxs)(`nav`, {
        "aria-label": `Bottom`,
        className: `fixed inset-x-0 bottom-0 z-40 grid grid-cols-5 border-t bg-card md:hidden`,
        children: [
          f.map((e) => {
            let t = u.find((t) => t.to === e);
            return (0, L.jsxs)(
              ve,
              {
                to: e,
                className: s(
                  `tap flex flex-col items-center justify-center gap-0.5 px-1 py-1.5 text-[11px] leading-tight`,
                  h(e) ? `font-semibold text-primary` : `text-muted-foreground`,
                ),
                children: [
                  (0, L.jsx)(t.icon, { className: `size-5`, "aria-hidden": !0 }),
                  (0, L.jsx)(`span`, { className: `text-center`, children: p(t) }),
                ],
              },
              e,
            );
          }),
          (0, L.jsxs)(`button`, {
            onClick: () => c(!0),
            "aria-expanded": o,
            className: `tap flex flex-col items-center justify-center gap-0.5 py-1.5 text-[11px] text-muted-foreground`,
            children: [(0, L.jsx)(_l, { className: `size-5`, "aria-hidden": !0 }), n.workspace === `student` ? a(`more`) : `More`],
          }),
        ],
      }),
      o &&
        (0, L.jsx)(`div`, {
          className: `fixed inset-0 z-[55] bg-foreground/40 md:hidden`,
          onClick: () => c(!1),
          children: (0, L.jsxs)(`div`, {
            role: `dialog`,
            "aria-modal": `true`,
            "aria-label": `More`,
            className: `absolute inset-x-0 bottom-0 max-h-[75vh] overflow-y-auto rounded-t-2xl bg-card p-4`,
            onClick: (e) => e.stopPropagation(),
            children: [
              (0, L.jsxs)(`div`, {
                className: `mb-2 flex items-center justify-between`,
                children: [
                  (0, L.jsx)(`strong`, { children: n.workspace === `student` ? a(`more`) : `More` }),
                  (0, L.jsx)(`button`, {
                    onClick: () => c(!1),
                    "aria-label": `Close`,
                    className: `tap grid place-items-center`,
                    children: (0, L.jsx)(Pl, { className: `size-5` }),
                  }),
                ],
              }),
              (0, L.jsx)(`ul`, {
                className: `grid grid-cols-2 gap-2`,
                children: u
                  .filter((e) => !f.includes(e.to))
                  .map((e) =>
                    (0, L.jsx)(
                      `li`,
                      {
                        children: (0, L.jsxs)(ve, {
                          to: e.to,
                          onClick: () => c(!1),
                          className: `tap flex items-center gap-2 rounded-lg border px-3 py-2 text-sm`,
                          children: [(0, L.jsx)(e.icon, { className: `size-4`, "aria-hidden": !0 }), p(e)],
                        }),
                      },
                      e.to,
                    ),
                  ),
              }),
            ],
          }),
        }),
      (0, L.jsx)(Kl, {}),
    ],
  });
}
function Jl() {
  return (0, L.jsx)(`div`, {
    className: `flex min-h-screen items-center justify-center bg-background px-4`,
    children: (0, L.jsxs)(`div`, {
      className: `max-w-md text-center`,
      children: [
        (0, L.jsx)(`h1`, { className: `text-5xl font-bold text-foreground`, children: `404` }),
        (0, L.jsx)(`p`, { className: `mt-2 text-sm text-muted-foreground`, children: `This prototype screen does not exist.` }),
        (0, L.jsx)(ve, {
          to: `/`,
          className: `mt-6 inline-flex rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground`,
          children: `Go home`,
        }),
      ],
    }),
  });
}
function Yl({ error: e, reset: t }) {
  let n = Fe();
  return (
    (0, I.useEffect)(() => {
      cl(e, { boundary: `tanstack_root_error_component` });
    }, [e]),
    (0, L.jsx)(`div`, {
      className: `flex min-h-screen items-center justify-center bg-background px-4`,
      children: (0, L.jsxs)(`div`, {
        className: `max-w-md text-center`,
        children: [
          (0, L.jsx)(`h1`, { className: `text-xl font-semibold text-foreground`, children: `This page didn't load` }),
          (0, L.jsx)(`button`, {
            onClick: () => {
              (n.invalidate(), t());
            },
            className: `mt-6 rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground`,
            children: `Try again`,
          }),
        ],
      }),
    })
  );
}
var J = ws()({
  head: () => ({
    meta: [
      { charSet: `utf-8` },
      { name: `viewport`, content: `width=device-width, initial-scale=1` },
      { title: `Nipuna LMS Vision — Interactive Prototype` },
      { name: `description`, content: `Sample-data interactive prototype of the Nipuna Technologies LMS.` },
      { name: `robots`, content: `noindex, nofollow` },
      { property: `og:type`, content: `website` },
      { name: `twitter:card`, content: `summary` },
    ],
    links: [
      { rel: `preconnect`, href: `https://fonts.googleapis.com` },
      { rel: `preconnect`, href: `https://fonts.gstatic.com`, crossOrigin: `anonymous` },
      {
        rel: `stylesheet`,
        href: `https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=Noto+Sans+Telugu:wght@400;500;600;700&display=swap`,
      },
      { rel: `stylesheet`, href: sl },
      { rel: `icon`, href: `/favicon.ico`, type: `image/x-icon` },
    ],
  }),
  shellComponent: Xl,
  component: Zl,
  notFoundComponent: Jl,
  errorComponent: Yl,
});
function Xl({ children: e }) {
  return (0, L.jsxs)(`html`, {
    lang: `en`,
    children: [(0, L.jsx)(`head`, { children: (0, L.jsx)(Qs, {}) }), (0, L.jsxs)(`body`, { children: [e, (0, L.jsx)($s, {})] })],
  });
}
function Zl() {
  let { queryClient: e } = J.useRouteContext();
  return (0, L.jsx)(ol, { client: e, children: (0, L.jsx)(n, { children: (0, L.jsx)(ql, { children: (0, L.jsx)(Rs, {}) }) }) });
}
function Y(e, t) {
  let n = `${e} — Nipuna LMS Prototype`;
  return {
    meta: [
      { title: n },
      { name: `description`, content: t },
      { property: `og:title`, content: n },
      { property: `og:description`, content: t },
      { property: `og:type`, content: `website` },
      { name: `twitter:card`, content: `summary` },
    ],
  };
}
var Ql = `modulepreload`,
  $l = function (e) {
    return `/` + e;
  },
  eu = {},
  X = function (e, t, n) {
    let r = Promise.resolve();
    if (t && t.length > 0) {
      let e = document.getElementsByTagName(`link`),
        i = document.querySelector(`meta[property=csp-nonce]`),
        a = i?.nonce || i?.getAttribute(`nonce`);
      function o(e) {
        return Promise.all(
          e.map((e) =>
            Promise.resolve(e).then(
              (e) => ({ status: `fulfilled`, value: e }),
              (e) => ({ status: `rejected`, reason: e }),
            ),
          ),
        );
      }
      function s(e) {
        return import.meta.resolve ? import.meta.resolve(e) : new URL(e, import.meta.url).href;
      }
      r = o(
        t.map((t) => {
          if (((t = $l(t, n)), (t = s(t)), t in eu)) return;
          eu[t] = !0;
          let r = t.endsWith(`.css`);
          for (let n = e.length - 1; n >= 0; n--) {
            let i = e[n];
            if (i.href === t && (!r || i.rel === `stylesheet`)) return;
          }
          let i = document.createElement(`link`);
          if (
            ((i.rel = r ? `stylesheet` : Ql),
            r || (i.as = `script`),
            (i.crossOrigin = ``),
            (i.href = t),
            a && i.setAttribute(`nonce`, a),
            document.head.appendChild(i),
            r)
          )
            return new Promise((e, n) => {
              (i.addEventListener(`load`, e), i.addEventListener(`error`, () => n(Error(`Unable to preload CSS for ${t}`))));
            });
        }),
      );
    }
    function i(e) {
      let t = new Event(`vite:preloadError`, { cancelable: !0 });
      if (((t.payload = e), window.dispatchEvent(t), !t.defaultPrevented)) throw e;
    }
    return r.then((t) => {
      for (let e of t || []) e.status === `rejected` && i(e.reason);
      return e().catch(i);
    });
  },
  tu = z(`/`)({
    head: () => Y(`Prototype Entry`, `Choose a simulated UAT role to explore the Nipuna LMS interactive prototype.`),
    component: B(() => X(() => import(`./routes-ClyrMQCX.js`), __vite__mapDeps([0, 1, 2, 3])), `component`),
  }),
  nu = z(`/ask-nipuna`)({
    head: () => Y(`Ask Nipuna`, `Simulated student study assistant with sources, scope and usage limits.`),
    component: B(() => X(() => import(`./ask-nipuna-Dn3XZcc9.js`), __vite__mapDeps([4, 1, 5])), `component`),
  }),
  ru = z(`/assignments`)({
    head: () => Y(`Assignments`, `Upcoming, due, submitted, under-review and reviewed assignments.`),
    component: B(() => X(() => import(`./assignments-DSft1sr-.js`), __vite__mapDeps([6, 1, 2, 3])), `component`),
  }),
  iu = z(`/attendance`)({
    head: () => Y(`Attendance`, `Attendance per actual Class Session with trainer-confirmed state and approved recovery.`),
    component: B(() => X(() => import(`./attendance-BWIdZk5K.js`), __vite__mapDeps([7, 1])), `component`),
  }),
  au = z(`/career`)({
    head: () => Y(`Placement & Career Support`, `Career profile, CVs, approved opportunities, applications and outcomes.`),
    component: B(() => X(() => import(`./career-DRmN2Qv7.js`), __vite__mapDeps([8, 1])), `component`),
  }),
  ou = z(`/certificates`)({
    head: () => Y(`Certificates`, `Course Completion and Internship certificate status from the LMS Certificate Register.`),
    component: B(() => X(() => import(`./certificates-9xYNJbdc.js`), __vite__mapDeps([9, 1, 10])), `component`),
  }),
  su = z(`/dashboard`)({
    head: () => Y(`Student Home`, `Next class, due work and course progress for the sample student.`),
    component: B(() => X(() => import(`./dashboard-CxRbYDf5.js`), __vite__mapDeps([11, 1, 2, 3])), `component`),
  }),
  cu = z(`/finance`)({
    head: () => Y(`Fees & Receipts`, `Read-only Admission, verified receipt and dues summary from the CRM.`),
    component: B(() => X(() => import(`./finance-CDHm91_U.js`), __vite__mapDeps([12, 1])), `component`),
  }),
  lu = z(`/founder`)({
    head: () => Y(`Founder / CEO Overview`, `Management overview of LMS academic delivery across branches.`),
    component: B(() => X(() => import(`./founder-CLoqGZbL.js`), __vite__mapDeps([13, 1, 2, 3, 14])), `component`),
  }),
  uu = z(`/login`)({
    head: () => Y(`Student Login & Activation`, `Sample student sign-in, account activation and course access release states.`),
    component: B(() => X(() => import(`./login-Y4AtX3yO.js`), __vite__mapDeps([15, 1])), `component`),
  }),
  du = z(`/my-courses`)({
    head: () =>
      Y(`My Courses`, `All course enrolments under one Student Master — combo, standalone, complimentary and separately purchased.`),
    component: B(() => X(() => import(`./my-courses-D741ow-R.js`), __vite__mapDeps([16, 1, 2, 3])), `component`),
  }),
  fu = z(`/notifications`)({
    head: () => Y(`Notifications`, `In-app notifications with separate delivery, read, acknowledged and action states.`),
    component: B(() => X(() => import(`./notifications-BNSealLt.js`), __vite__mapDeps([17, 1, 18])), `component`),
  }),
  pu = z(`/profile`)({
    head: () => Y(`Profile`, `Identity, language preference, devices, sessions and recovery status.`),
    component: B(() => X(() => import(`./profile-DM59gAzG.js`), __vite__mapDeps([19, 1])), `component`),
  }),
  mu = z(`/progress`)({
    head: () => Y(`Progress`, `Four separate progress measures: delivery, attendance, required learning, engagement.`),
    component: B(() => X(() => import(`./progress-CP6yqREV.js`), __vite__mapDeps([20, 1])), `component`),
  }),
  hu = z(`/recordings`)({
    head: () => Y(`Recordings`, `Class recordings mapped to actual sessions with access expiry and download policy.`),
    component: B(() => X(() => import(`./recordings-DjSzc1l_.js`), __vite__mapDeps([21, 1])), `component`),
  }),
  gu = z(`/resources`)({
    head: () => Y(`Content Library`, `PDFs, notes, datasets, code, labs and links for your enrolled courses.`),
    component: B(() => X(() => import(`./resources-Bip_DQfs.js`), __vite__mapDeps([22, 1])), `component`),
  }),
  _u = z(`/results`)({
    head: () => Y(`Results`, `Published academic results, distinguished from provisional/pending.`),
    component: B(() => X(() => import(`./results-DyLfAo-3.js`), __vite__mapDeps([23, 1])), `component`),
  }),
  vu = z(`/schedule`)({
    head: () => Y(`Schedule`, `Upcoming classes with IST timing, mode, trainer and branch.`),
    component: B(() => X(() => import(`./schedule-Cx_QC5sF.js`), __vite__mapDeps([24, 1, 2, 3])), `component`),
  }),
  yu = z(`/support`)({
    head: () => Y(`Support`, `Academic, LMS and account support requests with named owners.`),
    component: B(() => X(() => import(`./support-o0Ri-TQY.js`), __vite__mapDeps([25, 1])), `component`),
  }),
  bu = z(`/tests`)({
    head: () => Y(`Tests & Coding`, `Practice quizzes, module/final tests, coding exercises, mock tests and interviews.`),
    component: B(() => X(() => import(`./tests-BoSIJ8ii.js`), __vite__mapDeps([26, 1, 2, 3])), `component`),
  }),
  xu = z(`/academic/`)({
    head: () => Y(`Academic Coordinator`, `Delivery readiness, batches, reviews and exceptions for the branch.`),
    component: B(() => X(() => import(`./academic.index-CAoMB3z5.js`), __vite__mapDeps([27, 1, 2, 3, 14])), `component`),
  }),
  Su = z(`/academic/assessments`)({
    head: () => Y(`Assignment & Assessment Review`, `Moderate assessments and publish academic results.`),
    component: B(() => X(() => import(`./academic.assessments-eRl97w66.js`), __vite__mapDeps([28, 1, 14])), `component`),
  }),
  Cu = z(`/academic/batches`)({
    head: () => Y(`Batch Management`, `Batches, trainer assignment and batch allocation review checks.`),
    component: B(() => X(() => import(`./academic.batches-D0dgfD0p.js`), __vite__mapDeps([29, 1, 14])), `component`),
  }),
  wu = z(`/academic/certificates`)({
    head: () => Y(`Certificate Eligibility`, `Certificate eligibility workflow from the LMS Certificate Register.`),
    component: B(() => X(() => import(`./academic.certificates-O6WueR-L.js`), __vite__mapDeps([30, 1, 10, 14])), `component`),
  }),
  Tu = z(`/academic/completion`)({
    head: () => Y(`Completion Review`, `Evidence-based course completion review.`),
    component: B(() => X(() => import(`./academic.completion-BN51eLT3.js`), __vite__mapDeps([31, 1, 14])), `component`),
  }),
  Eu = z(`/academic/content-review`)({
    head: () => Y(`Content Review`, `Review trainer-submitted content before release to students.`),
    component: B(() => X(() => import(`./academic.content-review-BJjsMewK.js`), __vite__mapDeps([32, 1, 14])), `component`),
  }),
  Du = z(`/academic/curriculum`)({
    head: () => Y(`Curriculum Versions`, `Course curriculum versions and delivery readiness.`),
    component: B(() => X(() => import(`./academic.curriculum-Cir6Ir1_.js`), __vite__mapDeps([33, 1, 14])), `component`),
  }),
  Ou = z(`/academic/exceptions`)({
    head: () => Y(`Exceptions & Recovery`, `Academic exception and recovery queue.`),
    component: B(() => X(() => import(`./academic.exceptions-D2HN2vCb.js`), __vite__mapDeps([34, 1, 14])), `component`),
  }),
  ku = z(`/academic/progress`)({
    head: () => Y(`Attendance & Progress`, `Four separate progress measures per student.`),
    component: B(() => X(() => import(`./academic.progress-j4dQPbf0.js`), __vite__mapDeps([35, 1, 14])), `component`),
  }),
  Au = z(`/academic/recording-exceptions`)({
    head: () => Y(`Recording Exceptions`, `Partial, held and unavailable recordings mapped to class sessions.`),
    component: B(() => X(() => import(`./academic.recording-exceptions-By9A6VjL.js`), __vite__mapDeps([36, 1, 14])), `component`),
  }),
  ju = z(`/academic/reports`)({
    head: () => Y(`Academic Reports`, `Delivery, attendance, completion and certificate reports.`),
    component: B(() => X(() => import(`./academic.reports-DyxCRK4Z.js`), __vite__mapDeps([37, 1, 14])), `component`),
  }),
  Mu = z(`/academic/schedule`)({
    head: () => Y(`Schedule & Class Sessions`, `Scheduled live classes and actual class sessions with Meet association.`),
    component: B(() => X(() => import(`./academic.schedule-BkwGdppk.js`), __vite__mapDeps([38, 1, 14])), `component`),
  }),
  Nu = z(`/academic/support`)({
    head: () => Y(`Academic Support`, `Academic support requests with named owners.`),
    component: B(() => X(() => import(`./academic.support-CECWt1gT.js`), __vite__mapDeps([39, 1, 14])), `component`),
  }),
  Pu = z(`/admin/`)({
    head: () => Y(`Super Admin`, `All-branch readiness, sync status, provisioning and exception overview.`),
    component: B(() => X(() => import(`./admin.index-CckRYkvK.js`), __vite__mapDeps([40, 1, 2, 3, 14])), `component`),
  }),
  Fu = z(`/admin/exceptions`)({
    head: () => Y(`Exception Queues`, `All-branch Meet/recording, access, sync and provisioning exceptions.`),
    component: B(() => X(() => import(`./admin.exceptions-CxbBrwiH.js`), __vite__mapDeps([41, 1, 14])), `component`),
  }),
  Iu = z(`/admin/integrations`)({
    head: () => Y(`Integration Readiness`, `Requirement, configuration and operational verification per integration.`),
    component: B(() => X(() => import(`./admin.integrations-BUQk2JLq.js`), __vite__mapDeps([42, 1, 14, 43])), `component`),
  }),
  Lu = z(`/admin/security`)({
    head: () => Y(`Security Readiness`, `Security and access requirements with configuration and verification status.`),
    component: B(() => X(() => import(`./admin.security-CIDXfB18.js`), __vite__mapDeps([44, 1, 14, 43])), `component`),
  }),
  Ru = { Guntur: `trainer@nipunatechnologies.com`, Vijayawada: `contactus@nipunatechnologies.com` },
  zu = [
    { code: `NIT-CRS-018`, name: `Data Science with Python, SQL, Machine Learning & Applied AI` },
    { code: `NIT-CRS-047`, name: `Java Full Stack Developer` },
    { code: `NIT-CRS-052`, name: `Python Full Stack Developer` },
    { code: `NIT-CRS-007`, name: `AWS with DevOps` },
    { code: `NIT-CRS-019`, name: `Microsoft Power BI Data Analytics & Business Intelligence` },
  ],
  Bu = {
    masterId: `NIT-STU-2026-004182`,
    name: `Sample Student — Anvitha K.`,
    nameTe: `నమూనా విద్యార్థి — అన్విత కె.`,
    email: `anvitha.sample@example.test`,
    mobile: `+91 98XXX XX417 (shared family mobile — not identity proof)`,
    originalBranch: `Guntur`,
    serviceBranch: `Guntur`,
    preferredLanguage: `English / తెలుగు`,
    activation: `Activated`,
    mfa: `Optional — not configured`,
  },
  Vu = [
    {
      id: `enr-001`,
      kind: `Combo (3 + 1)`,
      code: `NIT-CRS-018`,
      name: `Data Science with Python, SQL, Machine Learning & Applied AI`,
      admissionRef: `ADM-GNT-2026-000214 (CRM)`,
      serviceBranch: `Guntur`,
      collectingBranch: `Guntur`,
      batch: `NIT-GNT-BAT-2026-000001`,
      status: `Active`,
      trainers: [`Trainer R. Sample`, `Trainer M. Demo`],
      curriculum: `Parent Programme v2026.1`,
      mode: `Classroom + Live Online`,
      joiningDate: `12 Jan 2026`,
      progress: 46,
      certificate: `Not Yet Eligible`,
      tracks: [
        {
          id: `trk-py`,
          code: `NIT-CRS-018/T1`,
          name: `Python & SQL Foundations`,
          role: `Main track`,
          curriculum: `Track CV 3.2`,
          progress: 88,
        },
        { id: `trk-ml`, code: `NIT-CRS-018/T2`, name: `Machine Learning`, role: `Main track`, curriculum: `Track CV 2.4`, progress: 41 },
        { id: `trk-ai`, code: `NIT-CRS-018/T3`, name: `Applied AI`, role: `Main track`, curriculum: `Track CV 1.1`, progress: 8 },
        {
          id: `trk-bi`,
          code: `NIT-CRS-019`,
          name: `Microsoft Power BI Data Analytics & Business Intelligence`,
          role: `Included booster`,
          curriculum: `Booster CV 1.3`,
          progress: null,
        },
      ],
    },
    {
      id: `enr-002`,
      kind: `Separately purchased`,
      code: `NIT-CRS-007`,
      name: `AWS with DevOps`,
      admissionRef: `ADM-VIJ-2026-000088 (CRM)`,
      serviceBranch: `Vijayawada`,
      collectingBranch: `Guntur`,
      batch: `NIT-VIJ-BAT-2026-000001`,
      status: `Allocated — awaiting first regular class`,
      trainers: [`Trainer S. Example`],
      curriculum: `CV 4.0`,
      mode: `Live Online`,
      joiningDate: null,
      progress: null,
      certificate: `Not Yet Eligible`,
    },
    {
      id: `enr-003`,
      kind: `Complimentary (promotional)`,
      code: `NIT-CRS-052`,
      name: `Python Full Stack Developer`,
      admissionRef: `Linked to ADM-GNT-2026-000214 (qualifying paid Admission)`,
      serviceBranch: `Guntur`,
      collectingBranch: `Guntur`,
      batch: null,
      status: `Curriculum Mapping Pending`,
      trainers: [],
      curriculum: null,
      mode: `Classroom`,
      joiningDate: null,
      progress: null,
      certificate: `Configuration Pending — completion rule not configured for complimentary offer`,
      linkedTo: `enr-001`,
    },
  ],
  Hu = [
    { id: `mod-ml-1`, trackId: `trk-ml`, title: `Supervised Learning`, topics: [`top-reg`, `top-cls`], status: `In delivery` },
    { id: `mod-ml-2`, trackId: `trk-ml`, title: `Model Evaluation`, topics: [`top-cv`], status: `Scheduled` },
    { id: `mod-py-3`, trackId: `trk-py`, title: `SQL for Analytics`, topics: [`top-join`], status: `Delivered` },
  ],
  Uu = [
    { id: `top-reg`, moduleId: `mod-ml-1`, title: `Linear & Logistic Regression`, sessions: [`ses-101`, `ses-102`], required: !0 },
    { id: `top-cls`, moduleId: `mod-ml-1`, title: `Decision Trees & Ensembles`, sessions: [`ses-103`], required: !0 },
    { id: `top-cv`, moduleId: `mod-ml-2`, title: `Cross-validation & Metrics`, sessions: [`ses-104`], required: !0 },
    { id: `top-join`, moduleId: `mod-py-3`, title: `Joins, Window Functions`, sessions: [`ses-090`], required: !0 },
  ],
  Wu = [
    {
      id: `ses-090`,
      topicId: `top-join`,
      title: `Window functions lab`,
      date: `02 Sep 2026`,
      time: `10:00–12:00 IST`,
      mode: `Classroom`,
      trainer: `Trainer R. Sample`,
      branch: `Guntur`,
      batch: `NIT-GNT-BAT-2026-000001`,
      state: `Delivered`,
      recording: `Released`,
      attendance: `Present (trainer-confirmed)`,
    },
    {
      id: `ses-101`,
      topicId: `top-reg`,
      title: `Linear regression intuition`,
      date: `21 Sep 2026`,
      time: `10:00–12:00 IST`,
      mode: `Live Online`,
      trainer: `Trainer M. Demo`,
      branch: `Guntur`,
      batch: `NIT-GNT-BAT-2026-000001`,
      state: `Delivered`,
      recording: `Partial`,
      attendance: `Absent — recovery approved (REC-0041)`,
    },
    {
      id: `ses-102`,
      topicId: `top-reg`,
      title: `Logistic regression & odds`,
      date: `24 Sep 2026`,
      time: `10:00–12:00 IST`,
      mode: `Classroom`,
      trainer: `Trainer M. Demo`,
      branch: `Guntur`,
      batch: `NIT-GNT-BAT-2026-000001`,
      state: `Delivered`,
      recording: `Held`,
      attendance: `Present (trainer-confirmed)`,
    },
    {
      id: `ses-103`,
      topicId: `top-cls`,
      title: `Decision trees`,
      date: `28 Sep 2026`,
      time: `10:00–12:00 IST`,
      mode: `Live Online`,
      trainer: `Trainer M. Demo`,
      branch: `Guntur`,
      batch: `NIT-GNT-BAT-2026-000001`,
      state: `Scheduled`,
      recording: `Unavailable`,
      attendance: `Not yet marked`,
    },
    {
      id: `ses-104`,
      topicId: `top-cv`,
      title: `Cross-validation workshop`,
      date: `01 Oct 2026`,
      time: `14:00–16:00 IST`,
      mode: `Classroom`,
      trainer: `Trainer R. Sample`,
      branch: `Guntur`,
      batch: `NIT-GNT-BAT-2026-000001`,
      state: `Scheduled`,
      recording: `Unavailable`,
      attendance: `Not yet marked`,
    },
    {
      id: `ses-201`,
      topicId: `top-cv`,
      title: `AWS orientation (VIJ)`,
      date: `30 Sep 2026`,
      time: `18:00–19:30 IST`,
      mode: `Live Online`,
      trainer: `Trainer S. Example`,
      branch: `Vijayawada`,
      batch: `NIT-VIJ-BAT-2026-000001`,
      state: `Scheduled`,
      recording: `Unavailable`,
      attendance: `Not yet marked`,
    },
  ],
  Gu = [
    {
      id: `asg-11`,
      title: `Regression on housing dataset`,
      module: `Supervised Learning`,
      topic: `Linear & Logistic Regression`,
      required: !0,
      view: `Due`,
      release: `21 Sep 2026`,
      due: `29 Sep 2026 23:59 IST`,
      version: `—`,
      feedback: `—`,
      marks: `—`,
    },
    {
      id: `asg-12`,
      title: `Decision tree tuning notebook`,
      module: `Supervised Learning`,
      topic: `Decision Trees & Ensembles`,
      required: !0,
      view: `Upcoming`,
      release: `28 Sep 2026`,
      due: `05 Oct 2026 23:59 IST`,
      version: `—`,
      feedback: `—`,
      marks: `—`,
    },
    {
      id: `asg-09`,
      title: `SQL window functions set`,
      module: `SQL for Analytics`,
      topic: `Joins, Window Functions`,
      required: !0,
      view: `Reviewed`,
      release: `02 Sep 2026`,
      due: `09 Sep 2026`,
      version: `v2 (resubmitted 08 Sep)`,
      feedback: `Good partitioning; revisit RANK vs DENSE_RANK.`,
      marks: `18 / 20`,
    },
    {
      id: `asg-10`,
      title: `EDA mini report`,
      module: `SQL for Analytics`,
      topic: `Joins, Window Functions`,
      required: !1,
      view: `Under Review`,
      release: `10 Sep 2026`,
      due: `20 Sep 2026`,
      version: `v1 (19 Sep)`,
      feedback: `Awaiting trainer review`,
      marks: `—`,
    },
    {
      id: `asg-08`,
      title: `Pandas cleaning practice`,
      module: `Python Foundations`,
      topic: `DataFrames`,
      required: !1,
      view: `Submitted`,
      release: `25 Aug 2026`,
      due: `01 Sep 2026`,
      version: `v1 (31 Aug)`,
      feedback: `—`,
      marks: `—`,
    },
  ],
  Z = [
    { id: `tst-1`, title: `Regression practice quiz`, type: `Practice quiz`, status: `Available`, duration: `20 min` },
    { id: `tst-2`, title: `Supervised Learning module test`, type: `Module test`, status: `Scheduled 03 Oct 2026`, duration: `60 min` },
    { id: `tst-3`, title: `SQL coding exercise`, type: `Coding exercise`, status: `Submitted — receipt RCPT-T-00931`, duration: `45 min` },
    { id: `tst-4`, title: `Data Science mock test`, type: `Mock test`, status: `Not Released`, duration: `90 min` },
    { id: `tst-5`, title: `Mock interview — ML basics`, type: `Mock interview`, status: `Slot Confirmation Pending`, duration: `30 min` },
    { id: `tst-6`, title: `Final test — Track 1`, type: `Final test`, status: `Configuration Pending`, duration: `120 min` },
  ],
  Ku = [
    {
      no: `NIT-CERT-2026-000001`,
      type: `Course Completion Certificate`,
      course: `NIT-CRS-047 Java Full Stack Developer`,
      holder: `Sample Learner A (GNT)`,
      status: `Issued`,
      version: `v2 (reissue — name correction)`,
    },
    {
      no: `NIT-CERT-2026-000002`,
      type: `Internship Certificate`,
      course: `NIT-CRS-052 Python Full Stack Developer`,
      holder: `Sample Learner B (VIJ)`,
      status: `Issued`,
      version: `v1`,
    },
    {
      no: `—`,
      type: `Course Completion Certificate`,
      course: `NIT-CRS-018 Data Science … Applied AI`,
      holder: `Sample Student — Anvitha K.`,
      status: `Not Yet Eligible`,
      version: `—`,
    },
    {
      no: `—`,
      type: `Course Completion Certificate`,
      course: `NIT-CRS-019 Microsoft Power BI …`,
      holder: `Sample Learner C (GNT)`,
      status: `Eligibility Review`,
      version: `—`,
    },
    {
      no: `—`,
      type: `Internship Certificate`,
      course: `NIT-CRS-007 AWS with DevOps`,
      holder: `Sample Learner D (VIJ)`,
      status: `Awaiting Approval`,
      version: `—`,
    },
    {
      no: `—`,
      type: `Course Completion Certificate`,
      course: `NIT-CRS-047 Java Full Stack Developer`,
      holder: `Sample Learner E (VIJ)`,
      status: `Approved for Issue`,
      version: `Number allocated at first issue`,
    },
    {
      no: `NIT-CERT-2026-000001`,
      type: `Course Completion Certificate`,
      course: `NIT-CRS-047 Java Full Stack Developer`,
      holder: `Sample Learner A (GNT)`,
      status: `Superseded`,
      version: `v1 (superseded by v2)`,
    },
    {
      no: `NIT-CERT-2026-000003`,
      type: `Course Completion Certificate`,
      course: `NIT-CRS-019 Microsoft Power BI …`,
      holder: `Sample Learner F (GNT)`,
      status: `Revoked`,
      version: `v1 — revoked (record error, audited)`,
    },
  ],
  qu = [
    {
      id: `NIT-GNT-BAT-2026-000001`,
      course: `NIT-CRS-018`,
      branch: `Guntur`,
      curriculum: `Parent Programme v2026.1`,
      capacity: `24 / 30`,
      trainer: `Trainer R. Sample, Trainer M. Demo`,
      state: `Running`,
      readiness: `Ready`,
    },
    {
      id: `NIT-GNT-BAT-2026-000002`,
      course: `NIT-CRS-047`,
      branch: `Guntur`,
      curriculum: `CV 5.1`,
      capacity: `30 / 30`,
      trainer: `Trainer K. Sample`,
      state: `Full`,
      readiness: `Ready`,
    },
    {
      id: `NIT-GNT-BAT-2026-000003`,
      course: `NIT-CRS-052`,
      branch: `Guntur`,
      curriculum: `Curriculum Mapping Pending`,
      capacity: `3 / 25`,
      trainer: `Unassigned`,
      state: `Forming`,
      readiness: `Blocked — Recovery Owner: Academic Coordinator GNT`,
    },
    {
      id: `NIT-VIJ-BAT-2026-000001`,
      course: `NIT-CRS-007`,
      branch: `Vijayawada`,
      curriculum: `CV 4.0`,
      capacity: `18 / 25`,
      trainer: `Trainer S. Example`,
      state: `Starting 30 Sep`,
      readiness: `Meet organizer Pending Verification`,
    },
    {
      id: `NIT-VIJ-BAT-2026-000002`,
      course: `NIT-CRS-019`,
      branch: `Vijayawada`,
      curriculum: `CV 1.3`,
      capacity: `12 / 20`,
      trainer: `Trainer P. Demo`,
      state: `Running`,
      readiness: `Ready`,
    },
  ],
  Ju = [
    { name: `Sample Student — Anvitha K.`, batch: `NIT-GNT-BAT-2026-000001`, attendance: `86%`, flag: `Open — recording access question` },
    { name: `Sample Learner G.`, batch: `NIT-GNT-BAT-2026-000001`, attendance: `71%`, flag: `Open — attendance alert` },
    { name: `Sample Learner H.`, batch: `NIT-GNT-BAT-2026-000001`, attendance: `94%`, flag: `None` },
    { name: `Sample Learner I.`, batch: `NIT-GNT-BAT-2026-000001`, attendance: `Partial Data`, flag: `None` },
    { name: `Sample Learner J.`, batch: `NIT-VIJ-BAT-2026-000001`, attendance: `Not started`, flag: `Open — device access` },
  ],
  Yu = [
    {
      id: `RX-0012`,
      session: `ses-101`,
      batch: `NIT-GNT-BAT-2026-000001`,
      issue: `Partial recording — second hour missing`,
      status: `Partial`,
      owner: `Academic Coordinator GNT`,
    },
    {
      id: `RX-0013`,
      session: `ses-102`,
      batch: `NIT-GNT-BAT-2026-000001`,
      issue: `Held for review — whiteboard shows sample PII`,
      status: `Held`,
      owner: `Academic Coordinator GNT`,
    },
    {
      id: `RX-0014`,
      session: `ses-201`,
      batch: `NIT-VIJ-BAT-2026-000001`,
      issue: `Organizer account licence Pending Verification`,
      status: `Integration Unavailable`,
      owner: `Super Admin`,
    },
    {
      id: `RX-0015`,
      session: `ses-095`,
      batch: `NIT-VIJ-BAT-2026-000002`,
      issue: `No recording mapped to actual Class Session`,
      status: `Unavailable`,
      owner: `Academic Coordinator VIJ`,
    },
  ],
  Xu = z(`/assignments/$id`)({
    loader: ({ params: e }) => {
      let t = Gu.find((t) => t.id === e.id);
      if (!t) throw Oe();
      return t;
    },
    head: ({ loaderData: e }) => {
      let t = e ? `${e.title} — Assignment — Nipuna LMS Prototype` : `Not found`;
      return {
        meta: [
          { title: t },
          { name: `description`, content: `Assignment brief, submission and feedback.` },
          { property: `og:title`, content: t },
          { property: `og:description`, content: `Assignment brief, submission and feedback.` },
        ],
      };
    },
    component: B(() => X(() => import(`./assignments._id-CV61yK9r.js`), __vite__mapDeps([45, 1, 2, 3])), `component`),
  }),
  Zu = z(`/branch/`)({
    head: () => Y(`Branch Academic Dashboard`, `Branch manager academic overview.`),
    component: B(() => X(() => import(`./branch.index-JrHhf5qF.js`), __vite__mapDeps([46, 1, 2, 3, 14])), `component`),
  }),
  Qu = z(`/branch/operations`)({
    head: () => Y(`Branch Batches, Schedule & People`, `Batches, schedule exceptions, trainers and students for the branch.`),
    component: B(() => X(() => import(`./branch.operations-CeqicnuX.js`), __vite__mapDeps([47, 1, 14])), `component`),
  }),
  $u = z(`/branch/reports`)({
    head: () => Y(`Branch Certificates & Reports`, `Branch certificate register entries and academic reports.`),
    component: B(() => X(() => import(`./branch.reports-Dv88gjTg.js`), __vite__mapDeps([48, 1, 10, 14])), `component`),
  }),
  ed = z(`/branch/requests`)({
    head: () => Y(`Escalations & Access Extensions`, `Support escalations and recording/material access extension requests.`),
    component: B(() => X(() => import(`./branch.requests-zx90gJ9Y.js`), __vite__mapDeps([49, 1, 14])), `component`),
  }),
  td = z(`/courses/$enrolmentId`)({
    loader: ({ params: e }) => {
      let t = Vu.find((t) => t.id === e.enrolmentId);
      if (!t) throw Oe();
      return t;
    },
    head: ({ loaderData: e }) => {
      let t = e ? `${e.code} — Course Overview — Nipuna LMS Prototype` : `Not found`,
        n = e ? `Overview of ${e.name} enrolment (sample).` : `Enrolment not found`;
      return {
        meta: [
          { title: t },
          { name: `description`, content: n },
          { property: `og:title`, content: t },
          { property: `og:description`, content: n },
        ],
      };
    },
    component: B(() => X(() => import(`./courses._enrolmentId-BXEg_eXK.js`), __vite__mapDeps([50, 1, 2, 3])), `component`),
  }),
  nd = z(`/modules/$moduleId`)({
    loader: ({ params: e }) => {
      let t = Hu.find((t) => t.id === e.moduleId);
      if (!t) throw Oe();
      return t;
    },
    head: ({ loaderData: e }) => {
      let t = e ? `${e.title} — Module — Nipuna LMS Prototype` : `Not found`;
      return {
        meta: [
          { title: t },
          { name: `description`, content: `Module topics and sessions.` },
          { property: `og:title`, content: t },
          { property: `og:description`, content: `Module topics and sessions.` },
        ],
      };
    },
    component: B(() => X(() => import(`./modules._moduleId-CHLzrPyJ.js`), __vite__mapDeps([51, 1, 2, 3])), `component`),
  }),
  rd = z(`/sessions/$sessionId`)({
    loader: ({ params: e }) => {
      let t = Wu.find((t) => t.id === e.sessionId);
      if (!t) throw Oe();
      return t;
    },
    head: ({ loaderData: e }) => {
      let t = e ? `${e.title} — Class Session — Nipuna LMS Prototype` : `Not found`;
      return {
        meta: [
          { title: t },
          { name: `description`, content: `Actual class session details, recording and attendance.` },
          { property: `og:title`, content: t },
          { property: `og:description`, content: `Actual class session details, recording and attendance.` },
        ],
      };
    },
    component: B(() => X(() => import(`./sessions._sessionId-DEUFYrlA.js`), __vite__mapDeps([52, 1, 2, 3])), `component`),
  }),
  id = z(`/tests/$id`)({
    loader: ({ params: e }) => {
      let t = Z.find((t) => t.id === e.id);
      if (!t) throw Oe();
      return t;
    },
    head: ({ loaderData: e }) => {
      let t = e ? `${e.title} — Test — Nipuna LMS Prototype` : `Not found`;
      return {
        meta: [
          { title: t },
          { name: `description`, content: `Assessment question types with server-authoritative timer concept.` },
          { property: `og:title`, content: t },
          { property: `og:description`, content: `Assessment question types with server-authoritative timer concept.` },
        ],
      };
    },
    component: B(() => X(() => import(`./tests._id-CO8z7hK5.js`), __vite__mapDeps([53, 1, 2, 3])), `component`),
  }),
  ad = z(`/topics/$topicId`)({
    loader: ({ params: e }) => {
      let t = Uu.find((t) => t.id === e.topicId);
      if (!t) throw Oe();
      return t;
    },
    head: ({ loaderData: e }) => {
      let t = e ? `${e.title} — Topic — Nipuna LMS Prototype` : `Not found`;
      return {
        meta: [
          { title: t },
          { name: `description`, content: `Topic sessions and resources.` },
          { property: `og:title`, content: t },
          { property: `og:description`, content: `Topic sessions and resources.` },
        ],
      };
    },
    component: B(() => X(() => import(`./topics._topicId-C4jthJx0.js`), __vite__mapDeps([54, 1, 2, 3])), `component`),
  }),
  od = z(`/trainer/`)({
    head: () => Y(`Trainer — Today`, `Trainer dashboard: assigned sessions, reviews awaiting, support flags, and today's session flow.`),
    component: B(() => X(() => import(`./trainer.index-CtPUt7Ey.js`), __vite__mapDeps([55, 1, 2, 3])), `component`),
  }),
  sd = z(`/trainer/ask-nipuna`)({
    head: () => Y(`Trainer — Ask Nipuna`, `Simulated staff assistant for session prep and review.`),
    component: B(() => X(() => import(`./trainer.ask-nipuna-CGbz6jaN.js`), __vite__mapDeps([56, 1, 5])), `component`),
  }),
  cd = z(`/trainer/assessments`)({
    head: () => Y(`Trainer — Assessments`, `Tests, coding exercises, mock tests and interviews for assigned batches.`),
    component: B(() => X(() => import(`./trainer.assessments-yfmUBmha.js`), __vite__mapDeps([57, 1, 14])), `component`),
  }),
  ld = z(`/trainer/assignments`)({
    head: () => Y(`Trainer — Assignments`, `Create and release curriculum-linked assignments.`),
    component: B(() => X(() => import(`./trainer.assignments-De5FsjTc.js`), __vite__mapDeps([58, 1, 14])), `component`),
  }),
  ud = z(`/trainer/attendance`)({
    head: () => Y(`Trainer — Attendance`, `Mark trainer-confirmed attendance for an actual Class Session.`),
    component: B(() => X(() => import(`./trainer.attendance-il8K7KC2.js`), __vite__mapDeps([59, 1, 14])), `component`),
  }),
  dd = z(`/trainer/batches`)({
    head: () => Y(`Trainer — Batches`, `Batches assigned to the trainer.`),
    component: B(() => X(() => import(`./trainer.batches-z8Q27maM.js`), __vite__mapDeps([60, 1, 14])), `component`),
  }),
  fd = z(`/trainer/content`)({
    head: () => Y(`Trainer — Content`, `Upload and submit session content for academic review.`),
    component: B(() => X(() => import(`./trainer.content-DR-jyULw.js`), __vite__mapDeps([61, 1, 14])), `component`),
  }),
  pd = z(`/trainer/notifications`)({
    head: () => Y(`Trainer — Notifications`, `Trainer in-app notification centre.`),
    component: B(() => X(() => import(`./trainer.notifications-B2UuANiF.js`), __vite__mapDeps([62, 1, 18])), `component`),
  }),
  md = z(`/trainer/reports`)({
    head: () => Y(`Trainer — Reports`, `Delivery and attendance reports for assigned batches.`),
    component: B(() => X(() => import(`./trainer.reports-CrWQpz2q.js`), __vite__mapDeps([63, 1, 14])), `component`),
  }),
  hd = z(`/trainer/reviews`)({
    head: () => Y(`Trainer — Reviews`, `Submissions awaiting review with versioned feedback and marks.`),
    component: B(() => X(() => import(`./trainer.reviews-CR5VZMUx.js`), __vite__mapDeps([64, 1, 14])), `component`),
  }),
  gd = z(`/trainer/sessions`)({
    head: () => Y(`Trainer — Sessions`, `Scheduled and actual class sessions for assigned batches.`),
    component: B(() => X(() => import(`./trainer.sessions-DxoDcFGw.js`), __vite__mapDeps([65, 1, 14])), `component`),
  }),
  _d = z(`/trainer/students`)({
    head: () => Y(`Trainer — Students`, `Assigned students with attendance and support flags.`),
    component: B(() => X(() => import(`./trainer.students-CPfaddij.js`), __vite__mapDeps([66, 1, 14])), `component`),
  }),
  vd = z(`/trainer/support`)({
    head: () => Y(`Trainer — Support`, `Open support flags for assigned students.`),
    component: B(() => X(() => import(`./trainer.support-yS8ggzSo.js`), __vite__mapDeps([67, 1, 14])), `component`),
  }),
  yd = z(`/courses/$enrolmentId/tracks/$trackId`)({
    loader: ({ params: e }) => {
      let t = Vu.find((t) => t.id === e.enrolmentId),
        n = t?.tracks?.find((t) => t.id === e.trackId);
      if (!t || !n) throw Oe();
      return { e: t, t: n };
    },
    head: ({ loaderData: e }) => {
      let t = e ? `${e.t.name} — Combo Track — Nipuna LMS Prototype` : `Not found`;
      return {
        meta: [
          { title: t },
          { name: `description`, content: `Combo track view within the parent programme.` },
          { property: `og:title`, content: t },
          { property: `og:description`, content: `Combo track view within the parent programme.` },
        ],
      };
    },
    component: B(() => X(() => import(`./courses._enrolmentId.tracks._trackId-CEl94QK7.js`), __vite__mapDeps([68, 1, 2, 3])), `component`),
  }),
  bd = tu.update({ id: `/`, path: `/`, getParentRoute: () => J }),
  Q = nu.update({ id: `/ask-nipuna`, path: `/ask-nipuna`, getParentRoute: () => J }),
  xd = ru.update({ id: `/assignments`, path: `/assignments`, getParentRoute: () => J }),
  Sd = iu.update({ id: `/attendance`, path: `/attendance`, getParentRoute: () => J }),
  Cd = au.update({ id: `/career`, path: `/career`, getParentRoute: () => J }),
  wd = ou.update({ id: `/certificates`, path: `/certificates`, getParentRoute: () => J }),
  Td = su.update({ id: `/dashboard`, path: `/dashboard`, getParentRoute: () => J }),
  Ed = cu.update({ id: `/finance`, path: `/finance`, getParentRoute: () => J }),
  Dd = lu.update({ id: `/founder`, path: `/founder`, getParentRoute: () => J }),
  Od = uu.update({ id: `/login`, path: `/login`, getParentRoute: () => J }),
  kd = du.update({ id: `/my-courses`, path: `/my-courses`, getParentRoute: () => J }),
  Ad = fu.update({ id: `/notifications`, path: `/notifications`, getParentRoute: () => J }),
  jd = pu.update({ id: `/profile`, path: `/profile`, getParentRoute: () => J }),
  Md = mu.update({ id: `/progress`, path: `/progress`, getParentRoute: () => J }),
  Nd = hu.update({ id: `/recordings`, path: `/recordings`, getParentRoute: () => J }),
  $ = gu.update({ id: `/resources`, path: `/resources`, getParentRoute: () => J }),
  Pd = _u.update({ id: `/results`, path: `/results`, getParentRoute: () => J }),
  Fd = vu.update({ id: `/schedule`, path: `/schedule`, getParentRoute: () => J }),
  Id = yu.update({ id: `/support`, path: `/support`, getParentRoute: () => J }),
  Ld = bu.update({ id: `/tests`, path: `/tests`, getParentRoute: () => J }),
  Rd = xu.update({ id: `/academic/`, path: `/academic/`, getParentRoute: () => J }),
  zd = Su.update({ id: `/academic/assessments`, path: `/academic/assessments`, getParentRoute: () => J }),
  Bd = Cu.update({ id: `/academic/batches`, path: `/academic/batches`, getParentRoute: () => J }),
  Vd = wu.update({ id: `/academic/certificates`, path: `/academic/certificates`, getParentRoute: () => J }),
  Hd = Tu.update({ id: `/academic/completion`, path: `/academic/completion`, getParentRoute: () => J }),
  Ud = Eu.update({ id: `/academic/content-review`, path: `/academic/content-review`, getParentRoute: () => J }),
  Wd = Du.update({ id: `/academic/curriculum`, path: `/academic/curriculum`, getParentRoute: () => J }),
  Gd = Ou.update({ id: `/academic/exceptions`, path: `/academic/exceptions`, getParentRoute: () => J }),
  Kd = ku.update({ id: `/academic/progress`, path: `/academic/progress`, getParentRoute: () => J }),
  qd = Au.update({ id: `/academic/recording-exceptions`, path: `/academic/recording-exceptions`, getParentRoute: () => J }),
  Jd = ju.update({ id: `/academic/reports`, path: `/academic/reports`, getParentRoute: () => J }),
  Yd = Mu.update({ id: `/academic/schedule`, path: `/academic/schedule`, getParentRoute: () => J }),
  Xd = Nu.update({ id: `/academic/support`, path: `/academic/support`, getParentRoute: () => J }),
  Zd = Pu.update({ id: `/admin/`, path: `/admin/`, getParentRoute: () => J }),
  Qd = Fu.update({ id: `/admin/exceptions`, path: `/admin/exceptions`, getParentRoute: () => J }),
  $d = Iu.update({ id: `/admin/integrations`, path: `/admin/integrations`, getParentRoute: () => J }),
  ef = Lu.update({ id: `/admin/security`, path: `/admin/security`, getParentRoute: () => J }),
  tf = Xu.update({ id: `/$id`, path: `/$id`, getParentRoute: () => xd }),
  nf = Zu.update({ id: `/branch/`, path: `/branch/`, getParentRoute: () => J }),
  rf = Qu.update({ id: `/branch/operations`, path: `/branch/operations`, getParentRoute: () => J }),
  af = $u.update({ id: `/branch/reports`, path: `/branch/reports`, getParentRoute: () => J }),
  of = ed.update({ id: `/branch/requests`, path: `/branch/requests`, getParentRoute: () => J }),
  sf = td.update({ id: `/courses/$enrolmentId`, path: `/courses/$enrolmentId`, getParentRoute: () => J }),
  cf = nd.update({ id: `/modules/$moduleId`, path: `/modules/$moduleId`, getParentRoute: () => J }),
  lf = rd.update({ id: `/sessions/$sessionId`, path: `/sessions/$sessionId`, getParentRoute: () => J }),
  uf = id.update({ id: `/$id`, path: `/$id`, getParentRoute: () => Ld }),
  df = ad.update({ id: `/topics/$topicId`, path: `/topics/$topicId`, getParentRoute: () => J }),
  ff = od.update({ id: `/trainer/`, path: `/trainer/`, getParentRoute: () => J }),
  pf = sd.update({ id: `/trainer/ask-nipuna`, path: `/trainer/ask-nipuna`, getParentRoute: () => J }),
  mf = cd.update({ id: `/trainer/assessments`, path: `/trainer/assessments`, getParentRoute: () => J }),
  hf = ld.update({ id: `/trainer/assignments`, path: `/trainer/assignments`, getParentRoute: () => J }),
  gf = ud.update({ id: `/trainer/attendance`, path: `/trainer/attendance`, getParentRoute: () => J }),
  _f = dd.update({ id: `/trainer/batches`, path: `/trainer/batches`, getParentRoute: () => J }),
  vf = fd.update({ id: `/trainer/content`, path: `/trainer/content`, getParentRoute: () => J }),
  yf = pd.update({ id: `/trainer/notifications`, path: `/trainer/notifications`, getParentRoute: () => J }),
  bf = md.update({ id: `/trainer/reports`, path: `/trainer/reports`, getParentRoute: () => J }),
  xf = hd.update({ id: `/trainer/reviews`, path: `/trainer/reviews`, getParentRoute: () => J }),
  Sf = gd.update({ id: `/trainer/sessions`, path: `/trainer/sessions`, getParentRoute: () => J }),
  Cf = _d.update({ id: `/trainer/students`, path: `/trainer/students`, getParentRoute: () => J }),
  wf = vd.update({ id: `/trainer/support`, path: `/trainer/support`, getParentRoute: () => J }),
  Tf = yd.update({ id: `/tracks/$trackId`, path: `/tracks/$trackId`, getParentRoute: () => sf }),
  Ef = { AssignmentsIdRoute: tf },
  Df = xd._addFileChildren(Ef),
  Of = { TestsIdRoute: uf },
  kf = Ld._addFileChildren(Of),
  Af = { CoursesEnrolmentIdTracksTrackIdRoute: Tf },
  jf = {
    IndexRoute: bd,
    AskNipunaRoute: Q,
    AssignmentsRoute: Df,
    AttendanceRoute: Sd,
    CareerRoute: Cd,
    CertificatesRoute: wd,
    DashboardRoute: Td,
    FinanceRoute: Ed,
    FounderRoute: Dd,
    LoginRoute: Od,
    MyCoursesRoute: kd,
    NotificationsRoute: Ad,
    ProfileRoute: jd,
    ProgressRoute: Md,
    RecordingsRoute: Nd,
    ResourcesRoute: $,
    ResultsRoute: Pd,
    ScheduleRoute: Fd,
    SupportRoute: Id,
    TestsRoute: kf,
    AcademicAssessmentsRoute: zd,
    AcademicBatchesRoute: Bd,
    AcademicCertificatesRoute: Vd,
    AcademicCompletionRoute: Hd,
    AcademicContentReviewRoute: Ud,
    AcademicCurriculumRoute: Wd,
    AcademicExceptionsRoute: Gd,
    AcademicProgressRoute: Kd,
    AcademicRecordingExceptionsRoute: qd,
    AcademicReportsRoute: Jd,
    AcademicScheduleRoute: Yd,
    AcademicSupportRoute: Xd,
    AdminExceptionsRoute: Qd,
    AdminIntegrationsRoute: $d,
    AdminSecurityRoute: ef,
    BranchOperationsRoute: rf,
    BranchReportsRoute: af,
    BranchRequestsRoute: of,
    CoursesEnrolmentIdRoute: sf._addFileChildren(Af),
    ModulesModuleIdRoute: cf,
    SessionsSessionIdRoute: lf,
    TopicsTopicIdRoute: df,
    TrainerAskNipunaRoute: pf,
    TrainerAssessmentsRoute: mf,
    TrainerAssignmentsRoute: hf,
    TrainerAttendanceRoute: gf,
    TrainerBatchesRoute: _f,
    TrainerContentRoute: vf,
    TrainerNotificationsRoute: yf,
    TrainerReportsRoute: bf,
    TrainerReviewsRoute: xf,
    TrainerSessionsRoute: Sf,
    TrainerStudentsRoute: Cf,
    TrainerSupportRoute: wf,
    AcademicIndexRoute: Rd,
    AdminIndexRoute: Zd,
    BranchIndexRoute: nf,
    TrainerIndexRoute: ff,
  },
  Mf = J._addFileChildren(jf),
  Nf = () => Us({ routeTree: Mf, context: { queryClient: new il() }, scrollRestoration: !0, defaultPreloadStaleTime: 0 });
async function Pf() {
  let e = await Nf(),
    t;
  if (oc) {
    let n = await oc.getOptions();
    ((n.serializationAdapters = n.serializationAdapters ?? []),
      (window.__TSS_START_OPTIONS__ = n),
      (t = n.serializationAdapters),
      (e.options.defaultSsr = n.defaultSsr));
  } else ((t = []), (window.__TSS_START_OPTIONS__ = { serializationAdapters: t }));
  return (
    t.push(Ho),
    e.options.serializationAdapters && t.push(...e.options.serializationAdapters),
    e.update({ basepath: ``, serializationAdapters: t }),
    e.stores.matchesId.get().length || (await Go(e)),
    e
  );
}
var Ff = Pf;
async function If() {
  let e = await Ff();
  return (window.$_TSR?.h(), e);
}
var Lf;
function Rf() {
  return ((Lf ||= If()), (0, L.jsx)(qo, { promise: Lf, children: (e) => (0, L.jsx)(Ks, { router: e }) }));
}
var zf = ze();
(0, I.startTransition)(() => {
  (0, zf.hydrateRoot)(document, (0, L.jsx)(I.StrictMode, { children: (0, L.jsx)(Rf, {}) }));
});
export {
  qs as C,
  Ol as S,
  bs as T,
  Bu as _,
  nd as a,
  Ju as b,
  Gu as c,
  zu as d,
  Vu as f,
  Wu as g,
  Yu as h,
  rd as i,
  qu as l,
  Hu as m,
  ad as n,
  td as o,
  Ru as p,
  id as r,
  Xu as s,
  yd as t,
  Ku as u,
  Z as v,
  Rs as w,
  Ll as x,
  Uu as y,
};
