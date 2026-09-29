  d = o((e) => {
    var t = Symbol.for(`react.transitional.element`),
      n = Symbol.for(`react.fragment`);
    function r(e, n, r) {
      var i = null;
      if ((r !== void 0 && (i = `` + r), n.key !== void 0 && (i = `` + n.key), `key` in n))
        for (var a in ((r = {}), n)) a !== `key` && (r[a] = n[a]);
      else r = n;
      return ((n = r.ref), { $$typeof: t, type: e, key: i, ref: n === void 0 ? null : n, props: r });
    }
    ((e.Fragment = n), (e.jsx = r), (e.jsxs = r));
  }),
  f = o((e, t) => {
    t.exports = d();
  }),
  p = c(u(), 1),
  m = f(),
  h = [
    { id: `student`, label: `Student`, workspace: `student`, branch: `Guntur`, home: `/dashboard` },
    { id: `trainer-gnt`, label: `Trainer — Guntur`, workspace: `trainer`, branch: `Guntur`, home: `/trainer` },
    { id: `trainer-vij`, label: `Trainer — Vijayawada`, workspace: `trainer`, branch: `Vijayawada`, home: `/trainer` },
    { id: `ac-gnt`, label: `Academic Coordinator — Guntur`, workspace: `academic`, branch: `Guntur`, home: `/academic` },
    { id: `ac-vij`, label: `Academic Coordinator — Vijayawada`, workspace: `academic`, branch: `Vijayawada`, home: `/academic` },
    { id: `bm-gnt`, label: `Branch Manager — Guntur`, workspace: `branch`, branch: `Guntur`, home: `/branch` },
    { id: `bm-vij`, label: `Branch Manager — Vijayawada`, workspace: `branch`, branch: `Vijayawada`, home: `/branch` },
    { id: `super-admin`, label: `Super Admin`, workspace: `admin`, branch: `All authorised branches`, home: `/admin` },
    { id: `founder`, label: `Founder / CEO`, workspace: `founder`, branch: `All authorised branches`, home: `/founder` },
  ];
function g(e, t) {
  return e.workspace === t
    ? !0
    : e.workspace === `admin`
      ? [`academic`, `branch`, `admin`].includes(t)
      : e.workspace === `founder` && [`founder`, `admin`, `branch`].includes(t);
}
var _ = (0, p.createContext)(null);
function v({ children: e }) {
  let [t, n] = (0, p.useState)(`student`),
    [r, i] = (0, p.useState)(`en`),
    [a, o] = (0, p.useState)([]);
  ((0, p.useEffect)(() => {
    let e = window.localStorage.getItem(`nlms-role`),
      t = window.localStorage.getItem(`nlms-lang`);
    (e && h.some((t) => t.id === e) && n(e), (t === `en` || t === `te`) && i(t));
  }, []),
    (0, p.useEffect)(() => {
      document.documentElement.lang = r;
    }, [r]));
  let s = (0, p.useCallback)((e) => {
      (n(e), window.localStorage.setItem(`nlms-role`, e));
    }, []),
    c = (0, p.useCallback)((e) => {
      (i(e), window.localStorage.setItem(`nlms-lang`, e));
    }, []),
    l = (0, p.useCallback)((e, t = `sim`) => {
      let n = Date.now() + Math.floor(performance.now());
      (o((r) => [...r.slice(-2), { id: n, text: e, tone: t }]), setTimeout(() => o((e) => e.filter((e) => e.id !== n)), 6e3));
    }, []),
    u = h.find((e) => e.id === t);
  return (0, m.jsx)(_.Provider, { value: { role: u, setRole: s, lang: r, setLang: c, notify: l, toasts: a }, children: e });
}
function y() {
  let e = (0, p.useContext)(_);
  if (!e) throw Error(`useProto outside provider`);
  return e;
}
var b = (...e) =>
    e
      .filter((e, t, n) => !!e && e.trim() !== `` && n.indexOf(e) === t)
      .join(` `)
      .trim(),
  x = (e) => e.replace(/([a-z0-9])([A-Z])/g, `$1-$2`).toLowerCase(),
  S = (e) => e.replace(/^([A-Z])|[\s-_]+(\w)/g, (e, t, n) => (n ? n.toUpperCase() : t.toLowerCase())),
  C = (e) => {
    let t = S(e);
    return t.charAt(0).toUpperCase() + t.slice(1);
  },
  w = {
    xmlns: `http://www.w3.org/2000/svg`,
    width: 24,
    height: 24,
    viewBox: `0 0 24 24`,
    fill: `none`,
    stroke: `currentColor`,
    strokeWidth: 2,
    strokeLinecap: `round`,
    strokeLinejoin: `round`,
  },
  T = (e) => {
    for (let t in e) if (t.startsWith(`aria-`) || t === `role` || t === `title`) return !0;
    return !1;
  },
  E = (0, p.forwardRef)(
    (
      {
        color: e = `currentColor`,
        size: t = 24,
        strokeWidth: n = 2,
        absoluteStrokeWidth: r,
        className: i = ``,
        children: a,
        iconNode: o,
        ...s
      },
      c,
    ) =>
      (0, p.createElement)(
        `svg`,
        {
          ref: c,
          ...w,
          width: t,
          height: t,
          stroke: e,
          strokeWidth: r ? (Number(n) * 24) / Number(t) : n,
          className: b(`lucide`, i),
          ...(!a && !T(s) && { "aria-hidden": `true` }),
          ...s,
        },
        [...o.map(([e, t]) => (0, p.createElement)(e, t)), ...(Array.isArray(a) ? a : [a])],
      ),
  ),
  D = (e, t) => {
    let n = (0, p.forwardRef)(({ className: n, ...r }, i) =>
      (0, p.createElement)(E, { ref: i, iconNode: t, className: b(`lucide-${x(C(e))}`, `lucide-${e}`, n), ...r }),
    );
    return ((n.displayName = C(e)), n);
  },
  O = D(`circle-check`, [
    [`circle`, { cx: `12`, cy: `12`, r: `10`, key: `1mglay` }],
    [`path`, { d: `m9 12 2 2 4-4`, key: `dzmm74` }],
  ]),
  k = D(`circle-x`, [
    [`circle`, { cx: `12`, cy: `12`, r: `10`, key: `1mglay` }],
    [`path`, { d: `m15 9-6 6`, key: `1uzhvr` }],
    [`path`, { d: `m9 9 6 6`, key: `z0biqf` }],
  ]),
  A = D(`clock`, [
    [`circle`, { cx: `12`, cy: `12`, r: `10`, key: `1mglay` }],
    [`path`, { d: `M12 6v6l4 2`, key: `mmk7yg` }],
  ]),
  j = D(`cloud-off`, [
    [`path`, { d: `M10.94 5.274A7 7 0 0 1 15.71 10h1.79a4.5 4.5 0 0 1 4.222 6.057`, key: `1uxyv8` }],
    [`path`, { d: `M18.796 18.81A4.5 4.5 0 0 1 17.5 19H9A7 7 0 0 1 5.79 5.78`, key: `99tcn7` }],
    [`path`, { d: `m2 2 20 20`, key: `1ooewy` }],
  ]),
  M = D(`flask-conical`, [
    [
      `path`,
      { d: `M14 2v6a2 2 0 0 0 .245.96l5.51 10.08A2 2 0 0 1 18 22H6a2 2 0 0 1-1.755-2.96l5.51-10.08A2 2 0 0 0 10 8V2`, key: `18mbvz` },
    ],
    [`path`, { d: `M6.453 15h11.094`, key: `3shlmq` }],
    [`path`, { d: `M8.5 2h7`, key: `csnxdl` }],
  ]),
  N = D(`info`, [
    [`circle`, { cx: `12`, cy: `12`, r: `10`, key: `1mglay` }],
    [`path`, { d: `M12 16v-4`, key: `1dtifu` }],
    [`path`, { d: `M12 8h.01`, key: `e9boi3` }],
  ]),
  P = D(`loader-circle`, [[`path`, { d: `M21 12a9 9 0 1 1-6.219-8.56`, key: `13zald` }]]),
  ee = D(`lock`, [
    [`rect`, { width: `18`, height: `11`, x: `3`, y: `11`, rx: `2`, ry: `2`, key: `1w4ew1` }],
    [`path`, { d: `M7 11V7a5 5 0 0 1 10 0v4`, key: `fwvmzm` }],
  ]),
  F = D(`triangle-alert`, [
    [`path`, { d: `m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3`, key: `wmoenq` }],
    [`path`, { d: `M12 9v4`, key: `juzpu7` }],
    [`path`, { d: `M12 17h.01`, key: `p32p05` }],
  ]);
function te(e) {
  var t,
    n,
    r = ``;
  if (typeof e == `string` || typeof e == `number`) r += e;
  else if (typeof e == `object`)
    if (Array.isArray(e)) {
      var i = e.length;
      for (t = 0; t < i; t++) e[t] && (n = te(e[t])) && (r && (r += ` `), (r += n));
    } else for (n in e) e[n] && (r && (r += ` `), (r += n));
  return r;
}
function ne() {
  for (var e, t, n = 0, r = ``, i = arguments.length; n < i; n++) (e = arguments[n]) && (t = te(e)) && (r && (r += ` `), (r += t));
  return r;
}
var re = (e, t) => {
    let n = Array(e.length + t.length);
    for (let t = 0; t < e.length; t++) n[t] = e[t];
    for (let r = 0; r < t.length; r++) n[e.length + r] = t[r];
    return n;
  },
  ie = (e, t) => ({ classGroupId: e, validator: t }),
  I = (e = new Map(), t = null, n) => ({ nextPart: e, validators: t, classGroupId: n }),
  L = `-`,
  R = [],
  ae = `arbitrary..`,
  z = (e) => {
    let t = V(e),
      { conflictingClassGroups: n, conflictingClassGroupModifiers: r } = e;
    return {
      getClassGroupId: (e) => {
        if (e.startsWith(`[`) && e.endsWith(`]`)) return B(e);
        let n = e.split(L);
        return oe(n, +(n[0] === `` && n.length > 1), t);
      },
      getConflictingClassGroupIds: (e, t) => {
        if (t) {
          let t = r[e],
            i = n[e];
          return t ? (i ? re(i, t) : t) : i || R;
        }
        return n[e] || R;
      },
    };
  },
  oe = (e, t, n) => {
    if (e.length - t === 0) return n.classGroupId;
    let r = e[t],
      i = n.nextPart.get(r);
    if (i) {
      let n = oe(e, t + 1, i);
      if (n) return n;
    }
    let a = n.validators;
    if (a === null) return;
    let o = t === 0 ? e.join(L) : e.slice(t).join(L),
      s = a.length;
    for (let e = 0; e < s; e++) {
      let t = a[e];
      if (t.validator(o)) return t.classGroupId;
    }
  },
  B = (e) =>
    e.slice(1, -1).indexOf(`:`) === -1
      ? void 0
      : (() => {
          let t = e.slice(1, -1),
            n = t.indexOf(`:`),
            r = t.slice(0, n);
          return r ? ae + r : void 0;
        })(),
  V = (e) => {
    let { theme: t, classGroups: n } = e;
    return se(n, t);
  },
  se = (e, t) => {
    let n = I();
    for (let r in e) {
      let i = e[r];
      H(i, n, r, t);
    }
    return n;
  },
  H = (e, t, n, r) => {
    let i = e.length;
    for (let a = 0; a < i; a++) {
      let i = e[a];
      ce(i, t, n, r);
    }
  },
  ce = (e, t, n, r) => {
    if (typeof e == `string`) {
      le(e, t, n);
      return;
    }
    if (typeof e == `function`) {
      ue(e, t, n, r);
      return;
    }
    de(e, t, n, r);
  },
  le = (e, t, n) => {
    let r = e === `` ? t : fe(t, e);
    r.classGroupId = n;
  },
  ue = (e, t, n, r) => {
    if (pe(e)) {
      H(e(r), t, n, r);
      return;
    }
    (t.validators === null && (t.validators = []), t.validators.push(ie(n, e)));
  },
  de = (e, t, n, r) => {
    let i = Object.entries(e),
      a = i.length;
    for (let e = 0; e < a; e++) {
      let [a, o] = i[e];
      H(o, fe(t, a), n, r);
    }
  },
  fe = (e, t) => {
    let n = e,
      r = t.split(L),
      i = r.length;
    for (let e = 0; e < i; e++) {
      let t = r[e],
        i = n.nextPart.get(t);
      (i || ((i = I()), n.nextPart.set(t, i)), (n = i));
    }
    return n;
  },
  pe = (e) => `isThemeGetter` in e && e.isThemeGetter === !0,
  me = (e) => {
    if (e < 1) return { get: () => void 0, set: () => {} };
    let t = 0,
      n = Object.create(null),
      r = Object.create(null),
      i = (i, a) => {
        ((n[i] = a), t++, t > e && ((t = 0), (r = n), (n = Object.create(null))));
      };
    return {
      get(e) {
        let t = n[e];
        if (t !== void 0) return t;
        if ((t = r[e]) !== void 0) return (i(e, t), t);
      },
      set(e, t) {
        e in n ? (n[e] = t) : i(e, t);
      },
    };
  },
  he = `!`,
  ge = `:`,
  _e = [],
  ve = (e, t, n, r, i) => ({ modifiers: e, hasImportantModifier: t, baseClassName: n, maybePostfixModifierPosition: r, isExternal: i }),
  ye = (e) => {
    let { prefix: t, experimentalParseClassName: n } = e,
      r = (e) => {
        let t = [],
          n = 0,
          r = 0,
          i = 0,
          a,
          o = e.length;
        for (let s = 0; s < o; s++) {
          let o = e[s];
          if (n === 0 && r === 0) {
            if (o === ge) {
              (t.push(e.slice(i, s)), (i = s + 1));
              continue;
            }
            if (o === `/`) {
              a = s;
              continue;
            }
          }
          o === `[` ? n++ : o === `]` ? n-- : o === `(` ? r++ : o === `)` && r--;
        }
        let s = t.length === 0 ? e : e.slice(i),
          c = s,
          l = !1;
        s.endsWith(he) ? ((c = s.slice(0, -1)), (l = !0)) : s.startsWith(he) && ((c = s.slice(1)), (l = !0));
        let u = a && a > i ? a - i : void 0;
        return ve(t, l, c, u);
      };
    if (t) {
      let e = t + ge,
        n = r;
      r = (t) => (t.startsWith(e) ? n(t.slice(e.length)) : ve(_e, !1, t, void 0, !0));
    }
    if (n) {
      let e = r;
      r = (t) => n({ className: t, parseClassName: e });
    }
    return r;
  },
  be = (e) => {
    let t = new Map();
    return (
      e.orderSensitiveModifiers.forEach((e, n) => {
        t.set(e, 1e6 + n);
      }),
      (e) => {
        let n = [],
          r = [];
        for (let i = 0; i < e.length; i++) {
          let a = e[i],
            o = a[0] === `[`,
            s = t.has(a);
          o || s ? (r.length > 0 && (r.sort(), n.push(...r), (r = [])), n.push(a)) : r.push(a);
        }
        return (r.length > 0 && (r.sort(), n.push(...r)), n);
      }
    );
  },
  xe = (e) => ({ cache: me(e.cacheSize), parseClassName: ye(e), sortModifiers: be(e), postfixLookupClassGroupIds: Se(e), ...z(e) }),
  Se = (e) => {
    let t = Object.create(null),
      n = e.postfixLookupClassGroups;
    if (n) for (let e = 0; e < n.length; e++) t[n[e]] = !0;
    return t;
  },
  Ce = /\s+/,
  we = (e, t) => {
    let { parseClassName: n, getClassGroupId: r, getConflictingClassGroupIds: i, sortModifiers: a, postfixLookupClassGroupIds: o } = t,
      s = [],
      c = e.trim().split(Ce),
      l = ``;
    for (let e = c.length - 1; e >= 0; --e) {
      let t = c[e],
        { isExternal: u, modifiers: d, hasImportantModifier: f, baseClassName: p, maybePostfixModifierPosition: m } = n(t);
      if (u) {
        l = t + (l.length > 0 ? ` ` + l : l);
        continue;
      }
      let h = !!m,
        g;
      if (h) {
        g = r(p.substring(0, m));
        let e = g && o[g] ? r(p) : void 0;
        e && e !== g && ((g = e), (h = !1));
      } else g = r(p);
      if (!g) {
        if (!h) {
          l = t + (l.length > 0 ? ` ` + l : l);
          continue;
        }
        if (((g = r(p)), !g)) {
          l = t + (l.length > 0 ? ` ` + l : l);
          continue;
        }
        h = !1;
      }
      let _ = d.length === 0 ? `` : d.length === 1 ? d[0] : a(d).join(`:`),
        v = f ? _ + he : _,
        y = v + g;
      if (s.indexOf(y) > -1) continue;
      s.push(y);
      let b = i(g, h);
      for (let e = 0; e < b.length; ++e) {
        let t = b[e];
        s.push(v + t);
      }
      l = t + (l.length > 0 ? ` ` + l : l);
    }
    return l;
  },
  Te = (...e) => {
    let t = 0,
      n,
      r,
      i = ``;
    for (; t < e.length;) (n = e[t++]) && (r = Ee(n)) && (i && (i += ` `), (i += r));
    return i;
  },
  Ee = (e) => {
    if (typeof e == `string`) return e;
    let t,
      n = ``;
    for (let r = 0; r < e.length; r++) e[r] && (t = Ee(e[r])) && (n && (n += ` `), (n += t));
    return n;
  },
  De = (e, ...t) => {
    let n,
      r,
      i,
      a,
      o = (o) => ((n = xe(t.reduce((e, t) => t(e), e()))), (r = n.cache.get), (i = n.cache.set), (a = s), s(o)),
      s = (e) => {
        let t = r(e);
        if (t) return t;
        let a = we(e, n);
        return (i(e, a), a);
      };
    return ((a = o), (...e) => a(Te(...e)));
  },
  Oe = [],
  U = (e) => {
    let t = (t) => t[e] || Oe;
    return ((t.isThemeGetter = !0), t);
  },
  ke = /^\[(?:(\w[\w-]*):)?(.+)\]$/i,
  Ae = /^\((?:(\w[\w-]*):)?(.+)\)$/i,
  je = /^\d+(?:\.\d+)?\/\d+(?:\.\d+)?$/,
  Me = /^(\d+(\.\d+)?)?(xs|sm|md|lg|xl)$/,
  Ne = /\d+(%|px|r?em|[sdl]?v([hwib]|min|max)|pt|pc|in|cm|mm|cap|ch|ex|r?lh|cq(w|h|i|b|min|max))|\b(calc|min|max|clamp)\(.+\)|^0$/,
  Pe = /^(rgba?|hsla?|hwb|(ok)?(lab|lch)|color-mix)\(.+\)$/,
  Fe = /^(inset_)?-?((\d+)?\.?(\d+)[a-z]+|0)_-?((\d+)?\.?(\d+)[a-z]+|0)/,
  Ie = /^(url|image|image-set|cross-fade|element|(repeating-)?(linear|radial|conic)-gradient)\(.+\)$/,
  W = (e) => je.test(e),
  G = (e) => !!e && !Number.isNaN(Number(e)),
  K = (e) => !!e && Number.isInteger(Number(e)),
  Le = (e) => e.endsWith(`%`) && G(e.slice(0, -1)),
  q = (e) => Me.test(e),
  Re = () => !0,
  ze = (e) => Ne.test(e) && !Pe.test(e),
  Be = () => !1,
  Ve = (e) => Fe.test(e),
  He = (e) => Ie.test(e),
  Ue = (e) => !J(e) && !X(e),
  We = (e) =>
    e.startsWith(`@container`) &&
    ((e[10] === `/` && e[11] !== void 0) ||
      (e[11] === `s` && e[16] !== void 0 && e.startsWith(`-size/`, 10)) ||
      (e[11] === `n` && e[18] !== void 0 && e.startsWith(`-normal/`, 10))),
  Ge = (e) => Z(e, st, Be),
  J = (e) => ke.test(e),
  Y = (e) => Z(e, ct, ze),
  Ke = (e) => Z(e, lt, G),
  qe = (e) => Z(e, dt, Re),
  Je = (e) => Z(e, ut, Be),
  Ye = (e) => Z(e, at, Be),
  Xe = (e) => Z(e, ot, He),
  Ze = (e) => Z(e, ft, Ve),
  X = (e) => Ae.test(e),
  Qe = (e) => Q(e, ct),
  $e = (e) => Q(e, ut),
  et = (e) => Q(e, at),
  tt = (e) => Q(e, st),
  nt = (e) => Q(e, ot),
  rt = (e) => Q(e, ft, !0),
  it = (e) => Q(e, dt, !0),
  Z = (e, t, n) => {
    let r = ke.exec(e);
    return r ? (r[1] ? t(r[1]) : n(r[2])) : !1;
  },
  Q = (e, t, n = !1) => {
    let r = Ae.exec(e);
    return r ? (r[1] ? t(r[1]) : n) : !1;
  },
  at = (e) => e === `position` || e === `percentage`,
  ot = (e) => e === `image` || e === `url`,
  st = (e) => e === `length` || e === `size` || e === `bg-size`,
  ct = (e) => e === `length`,
  lt = (e) => e === `number`,
  ut = (e) => e === `family-name`,
  dt = (e) => e === `number` || e === `weight`,
  ft = (e) => e === `shadow`,
  pt = De(() => {
    let e = U(`color`),
      t = U(`font`),
      n = U(`text`),
      r = U(`font-weight`),
      i = U(`tracking`),
      a = U(`leading`),
      o = U(`breakpoint`),
      s = U(`container`),
      c = U(`spacing`),
      l = U(`radius`),
      u = U(`shadow`),
      d = U(`inset-shadow`),
      f = U(`text-shadow`),
      p = U(`drop-shadow`),
      m = U(`blur`),
      h = U(`perspective`),
      g = U(`aspect`),
      _ = U(`ease`),
      v = U(`animate`),
      y = () => [`auto`, `avoid`, `all`, `avoid-page`, `page`, `left`, `right`, `column`],
      b = () => [
        `center`,
        `top`,
        `bottom`,
        `left`,
        `right`,
        `top-left`,
        `left-top`,
        `top-right`,
        `right-top`,
        `bottom-right`,
        `right-bottom`,
        `bottom-left`,
        `left-bottom`,
      ],
      x = () => [...b(), X, J],
      S = () => [`auto`, `hidden`, `clip`, `visible`, `scroll`],
      C = () => [`auto`, `contain`, `none`],
      w = () => [X, J, c],
      T = () => [W, `full`, `auto`, ...w()],
      E = () => [K, `none`, `subgrid`, X, J],
      D = () => [`auto`, { span: [`full`, K, X, J] }, K, X, J],
      O = () => [K, `auto`, X, J],
      k = () => [`auto`, `min`, `max`, `fr`, X, J],
      A = () => [`start`, `end`, `center`, `between`, `around`, `evenly`, `stretch`, `baseline`, `center-safe`, `end-safe`],
      j = () => [`start`, `end`, `center`, `stretch`, `center-safe`, `end-safe`],
      M = () => [`auto`, ...w()],
      N = () => [W, `auto`, `full`, `dvw`, `dvh`, `lvw`, `lvh`, `svw`, `svh`, `min`, `max`, `fit`, ...w()],
      P = () => [W, `screen`, `full`, `dvw`, `lvw`, `svw`, `min`, `max`, `fit`, ...w()],
      ee = () => [W, `screen`, `full`, `lh`, `dvh`, `lvh`, `svh`, `min`, `max`, `fit`, ...w()],
      F = () => [e, X, J],
      te = () => [...b(), et, Ye, { position: [X, J] }],
      ne = () => [`no-repeat`, { repeat: [``, `x`, `y`, `space`, `round`] }],
      re = () => [`auto`, `cover`, `contain`, tt, Ge, { size: [X, J] }],
      ie = () => [Le, Qe, Y],
      I = () => [``, `none`, `full`, l, X, J],
      L = () => [``, G, Qe, Y],
      R = () => [`solid`, `dashed`, `dotted`, `double`],
      ae = () => [
        `normal`,
        `multiply`,
        `screen`,
        `overlay`,
        `darken`,
        `lighten`,
        `color-dodge`,
        `color-burn`,
        `hard-light`,
        `soft-light`,
        `difference`,
        `exclusion`,
        `hue`,
        `saturation`,
        `color`,
        `luminosity`,
      ],
      z = () => [G, Le, et, Ye],
      oe = () => [``, `none`, m, X, J],
      B = () => [`none`, G, X, J],
      V = () => [`none`, G, X, J],
      se = () => [G, X, J],
      H = () => [W, `full`, ...w()];
    return {
      cacheSize: 500,
      theme: {
        animate: [`spin`, `ping`, `pulse`, `bounce`],
        aspect: [`video`],
        blur: [q],
        breakpoint: [q],
        color: [Re],
        container: [q],
        "drop-shadow": [q],
        ease: [`in`, `out`, `in-out`],
        font: [Ue],
        "font-weight": [`thin`, `extralight`, `light`, `normal`, `medium`, `semibold`, `bold`, `extrabold`, `black`],
        "inset-shadow": [q],
        leading: [`none`, `tight`, `snug`, `normal`, `relaxed`, `loose`],
        perspective: [`dramatic`, `near`, `normal`, `midrange`, `distant`, `none`],
        radius: [q],
        shadow: [q],
        spacing: [`px`, G],
        text: [q],
        "text-shadow": [q],
        tracking: [`tighter`, `tight`, `normal`, `wide`, `wider`, `widest`],
      },
      classGroups: {
        aspect: [{ aspect: [`auto`, `square`, W, J, X, g] }],
        container: [`container`],
        "container-type": [{ "@container": [``, `normal`, `size`, X, J] }],
        "container-named": [We],
        columns: [{ columns: [G, J, X, s] }],
        "break-after": [{ "break-after": y() }],
        "break-before": [{ "break-before": y() }],
        "break-inside": [{ "break-inside": [`auto`, `avoid`, `avoid-page`, `avoid-column`] }],
        "box-decoration": [{ "box-decoration": [`slice`, `clone`] }],
        box: [{ box: [`border`, `content`] }],
        display: [
          `block`,
          `inline-block`,
          `inline`,
          `flex`,
          `inline-flex`,
          `table`,
          `inline-table`,
          `table-caption`,
          `table-cell`,
          `table-column`,
          `table-column-group`,
          `table-footer-group`,
          `table-header-group`,
          `table-row-group`,
          `table-row`,
          `flow-root`,
          `grid`,
          `inline-grid`,
          `contents`,
          `list-item`,
          `hidden`,
        ],
        sr: [`sr-only`, `not-sr-only`],
        float: [{ float: [`right`, `left`, `none`, `start`, `end`] }],
        clear: [{ clear: [`left`, `right`, `both`, `none`, `start`, `end`] }],
        isolation: [`isolate`, `isolation-auto`],
        "object-fit": [{ object: [`contain`, `cover`, `fill`, `none`, `scale-down`] }],
        "object-position": [{ object: x() }],
        overflow: [{ overflow: S() }],
        "overflow-x": [{ "overflow-x": S() }],
        "overflow-y": [{ "overflow-y": S() }],
        overscroll: [{ overscroll: C() }],
        "overscroll-x": [{ "overscroll-x": C() }],
        "overscroll-y": [{ "overscroll-y": C() }],
        position: [`static`, `fixed`, `absolute`, `relative`, `sticky`],
        inset: [{ inset: T() }],
        "inset-x": [{ "inset-x": T() }],
        "inset-y": [{ "inset-y": T() }],
        start: [{ "inset-s": T(), start: T() }],
        end: [{ "inset-e": T(), end: T() }],
        "inset-bs": [{ "inset-bs": T() }],
        "inset-be": [{ "inset-be": T() }],
        top: [{ top: T() }],
        right: [{ right: T() }],
        bottom: [{ bottom: T() }],
        left: [{ left: T() }],
        visibility: [`visible`, `invisible`, `collapse`],
        z: [{ z: [K, `auto`, X, J] }],
        basis: [{ basis: [W, `full`, `auto`, s, ...w()] }],
        "flex-direction": [{ flex: [`row`, `row-reverse`, `col`, `col-reverse`] }],
        "flex-wrap": [{ flex: [`nowrap`, `wrap`, `wrap-reverse`] }],
        flex: [{ flex: [G, W, `auto`, `initial`, `none`, J] }],
        grow: [{ grow: [``, G, X, J] }],
        shrink: [{ shrink: [``, G, X, J] }],
        order: [{ order: [K, `first`, `last`, `none`, X, J] }],
        "grid-cols": [{ "grid-cols": E() }],
        "col-start-end": [{ col: D() }],
        "col-start": [{ "col-start": O() }],
        "col-end": [{ "col-end": O() }],
        "grid-rows": [{ "grid-rows": E() }],
        "row-start-end": [{ row: D() }],
        "row-start": [{ "row-start": O() }],
        "row-end": [{ "row-end": O() }],
        "grid-flow": [{ "grid-flow": [`row`, `col`, `dense`, `row-dense`, `col-dense`] }],
        "auto-cols": [{ "auto-cols": k() }],
        "auto-rows": [{ "auto-rows": k() }],
        gap: [{ gap: w() }],
        "gap-x": [{ "gap-x": w() }],
        "gap-y": [{ "gap-y": w() }],
        "justify-content": [{ justify: [...A(), `normal`] }],
        "justify-items": [{ "justify-items": [...j(), `normal`] }],
        "justify-self": [{ "justify-self": [`auto`, ...j()] }],
        "align-content": [{ content: [`normal`, ...A()] }],
        "align-items": [{ items: [...j(), { baseline: [``, `last`] }] }],
        "align-self": [{ self: [`auto`, ...j(), { baseline: [``, `last`] }] }],
        "place-content": [{ "place-content": A() }],
        "place-items": [{ "place-items": [...j(), `baseline`] }],
        "place-self": [{ "place-self": [`auto`, ...j()] }],
        p: [{ p: w() }],
        px: [{ px: w() }],
        py: [{ py: w() }],
        ps: [{ ps: w() }],
        pe: [{ pe: w() }],
        pbs: [{ pbs: w() }],
        pbe: [{ pbe: w() }],
        pt: [{ pt: w() }],
        pr: [{ pr: w() }],
        pb: [{ pb: w() }],
        pl: [{ pl: w() }],
        m: [{ m: M() }],
        mx: [{ mx: M() }],
        my: [{ my: M() }],
        ms: [{ ms: M() }],
        me: [{ me: M() }],
        mbs: [{ mbs: M() }],
        mbe: [{ mbe: M() }],
        mt: [{ mt: M() }],
        mr: [{ mr: M() }],
        mb: [{ mb: M() }],
        ml: [{ ml: M() }],
        "space-x": [{ "space-x": w() }],
        "space-x-reverse": [`space-x-reverse`],
        "space-y": [{ "space-y": w() }],
        "space-y-reverse": [`space-y-reverse`],
        size: [{ size: N() }],
        "inline-size": [{ inline: [`auto`, ...P()] }],
        "min-inline-size": [{ "min-inline": [`auto`, ...P()] }],
        "max-inline-size": [{ "max-inline": [`none`, ...P()] }],
        "block-size": [{ block: [`auto`, ...ee()] }],
        "min-block-size": [{ "min-block": [`auto`, ...ee()] }],
        "max-block-size": [{ "max-block": [`none`, ...ee()] }],
        w: [{ w: [s, `screen`, ...N()] }],
        "min-w": [{ "min-w": [s, `screen`, `none`, ...N()] }],
        "max-w": [{ "max-w": [s, `screen`, `none`, `prose`, { screen: [o] }, ...N()] }],
        h: [{ h: [`screen`, `lh`, ...N()] }],
        "min-h": [{ "min-h": [`screen`, `lh`, `none`, ...N()] }],
        "max-h": [{ "max-h": [`screen`, `lh`, ...N()] }],
        "font-size": [{ text: [`base`, n, Qe, Y] }],
        "font-smoothing": [`antialiased`, `subpixel-antialiased`],
        "font-style": [`italic`, `not-italic`],
        "font-weight": [{ font: [r, it, qe] }],
        "font-stretch": [
          {
            "font-stretch": [
              `ultra-condensed`,
              `extra-condensed`,
              `condensed`,
              `semi-condensed`,
              `normal`,
              `semi-expanded`,
              `expanded`,
              `extra-expanded`,
              `ultra-expanded`,
              Le,
              J,
            ],
          },
        ],
        "font-family": [{ font: [$e, Je, t] }],
        "font-features": [{ "font-features": [J] }],
        "fvn-normal": [`normal-nums`],
        "fvn-ordinal": [`ordinal`],
        "fvn-slashed-zero": [`slashed-zero`],
        "fvn-figure": [`lining-nums`, `oldstyle-nums`],
        "fvn-spacing": [`proportional-nums`, `tabular-nums`],
        "fvn-fraction": [`diagonal-fractions`, `stacked-fractions`],
        tracking: [{ tracking: [i, X, J] }],
        "line-clamp": [{ "line-clamp": [G, `none`, X, Ke] }],
        leading: [{ leading: [a, ...w()] }],
        "list-image": [{ "list-image": [`none`, X, J] }],
        "list-style-position": [{ list: [`inside`, `outside`] }],
        "list-style-type": [{ list: [`disc`, `decimal`, `none`, X, J] }],
        "text-alignment": [{ text: [`left`, `center`, `right`, `justify`, `start`, `end`] }],
        "placeholder-color": [{ placeholder: F() }],
        "text-color": [{ text: F() }],
        "text-decoration": [`underline`, `overline`, `line-through`, `no-underline`],
        "text-decoration-style": [{ decoration: [...R(), `wavy`] }],
        "text-decoration-thickness": [{ decoration: [G, `from-font`, `auto`, X, Y] }],
        "text-decoration-color": [{ decoration: F() }],
        "underline-offset": [{ "underline-offset": [G, `auto`, X, J] }],
        "text-transform": [`uppercase`, `lowercase`, `capitalize`, `normal-case`],
        "text-overflow": [`truncate`, `text-ellipsis`, `text-clip`],
        "text-wrap": [{ text: [`wrap`, `nowrap`, `balance`, `pretty`] }],
        indent: [{ indent: w() }],
        "tab-size": [{ tab: [K, X, J] }],
        "vertical-align": [{ align: [`baseline`, `top`, `middle`, `bottom`, `text-top`, `text-bottom`, `sub`, `super`, X, J] }],
        whitespace: [{ whitespace: [`normal`, `nowrap`, `pre`, `pre-line`, `pre-wrap`, `break-spaces`] }],
        break: [{ break: [`normal`, `words`, `all`, `keep`] }],
        wrap: [{ wrap: [`break-word`, `anywhere`, `normal`] }],
        hyphens: [{ hyphens: [`none`, `manual`, `auto`] }],
        content: [{ content: [`none`, X, J] }],
        "bg-attachment": [{ bg: [`fixed`, `local`, `scroll`] }],
        "bg-clip": [{ "bg-clip": [`border`, `padding`, `content`, `text`] }],
        "bg-origin": [{ "bg-origin": [`border`, `padding`, `content`] }],
        "bg-position": [{ bg: te() }],
        "bg-repeat": [{ bg: ne() }],
        "bg-size": [{ bg: re() }],
        "bg-image": [
          {
            bg: [
              `none`,
              { linear: [{ to: [`t`, `tr`, `r`, `br`, `b`, `bl`, `l`, `tl`] }, K, X, J], radial: [``, X, J], conic: [K, X, J] },
              nt,
              Xe,
            ],
          },
        ],
        "bg-color": [{ bg: F() }],
        "gradient-from-pos": [{ from: ie() }],
        "gradient-via-pos": [{ via: ie() }],
        "gradient-to-pos": [{ to: ie() }],
        "gradient-from": [{ from: F() }],
        "gradient-via": [{ via: F() }],
        "gradient-to": [{ to: F() }],
        rounded: [{ rounded: I() }],
        "rounded-s": [{ "rounded-s": I() }],
        "rounded-e": [{ "rounded-e": I() }],
        "rounded-t": [{ "rounded-t": I() }],
        "rounded-r": [{ "rounded-r": I() }],
        "rounded-b": [{ "rounded-b": I() }],
        "rounded-l": [{ "rounded-l": I() }],
        "rounded-ss": [{ "rounded-ss": I() }],
        "rounded-se": [{ "rounded-se": I() }],
        "rounded-ee": [{ "rounded-ee": I() }],
        "rounded-es": [{ "rounded-es": I() }],
        "rounded-tl": [{ "rounded-tl": I() }],
        "rounded-tr": [{ "rounded-tr": I() }],
        "rounded-br": [{ "rounded-br": I() }],
        "rounded-bl": [{ "rounded-bl": I() }],
        "border-w": [{ border: L() }],
        "border-w-x": [{ "border-x": L() }],
        "border-w-y": [{ "border-y": L() }],
        "border-w-s": [{ "border-s": L() }],
        "border-w-e": [{ "border-e": L() }],
        "border-w-bs": [{ "border-bs": L() }],
        "border-w-be": [{ "border-be": L() }],
        "border-w-t": [{ "border-t": L() }],
        "border-w-r": [{ "border-r": L() }],
        "border-w-b": [{ "border-b": L() }],
        "border-w-l": [{ "border-l": L() }],
        "divide-x": [{ "divide-x": L() }],
        "divide-x-reverse": [`divide-x-reverse`],
        "divide-y": [{ "divide-y": L() }],
        "divide-y-reverse": [`divide-y-reverse`],
        "border-style": [{ border: [...R(), `hidden`, `none`] }],
        "divide-style": [{ divide: [...R(), `hidden`, `none`] }],
        "border-color": [{ border: F() }],
        "border-color-x": [{ "border-x": F() }],
        "border-color-y": [{ "border-y": F() }],
        "border-color-s": [{ "border-s": F() }],
        "border-color-e": [{ "border-e": F() }],
        "border-color-bs": [{ "border-bs": F() }],
        "border-color-be": [{ "border-be": F() }],
        "border-color-t": [{ "border-t": F() }],
        "border-color-r": [{ "border-r": F() }],
        "border-color-b": [{ "border-b": F() }],
        "border-color-l": [{ "border-l": F() }],
        "divide-color": [{ divide: F() }],
        "outline-style": [{ outline: [...R(), `none`, `hidden`] }],
        "outline-offset": [{ "outline-offset": [G, X, J] }],
        "outline-w": [{ outline: [``, G, Qe, Y] }],
        "outline-color": [{ outline: F() }],
        shadow: [{ shadow: [``, `none`, u, rt, Ze] }],
        "shadow-color": [{ shadow: F() }],
        "inset-shadow": [{ "inset-shadow": [`none`, d, rt, Ze] }],
        "inset-shadow-color": [{ "inset-shadow": F() }],
        "ring-w": [{ ring: L() }],
        "ring-w-inset": [`ring-inset`],
        "ring-color": [{ ring: F() }],
        "ring-offset-w": [{ "ring-offset": [G, Y] }],
        "ring-offset-color": [{ "ring-offset": F() }],
        "inset-ring-w": [{ "inset-ring": L() }],
        "inset-ring-color": [{ "inset-ring": F() }],
        "text-shadow": [{ "text-shadow": [`none`, f, rt, Ze] }],
        "text-shadow-color": [{ "text-shadow": F() }],
        opacity: [{ opacity: [G, X, J] }],
        "mix-blend": [{ "mix-blend": [...ae(), `plus-darker`, `plus-lighter`] }],
        "bg-blend": [{ "bg-blend": ae() }],
        "mask-clip": [{ "mask-clip": [`border`, `padding`, `content`, `fill`, `stroke`, `view`] }, `mask-no-clip`],
        "mask-composite": [{ mask: [`add`, `subtract`, `intersect`, `exclude`] }],
        "mask-image-linear-pos": [{ "mask-linear": [G] }],
        "mask-image-linear-from-pos": [{ "mask-linear-from": z() }],
        "mask-image-linear-to-pos": [{ "mask-linear-to": z() }],
        "mask-image-linear-from-color": [{ "mask-linear-from": F() }],
        "mask-image-linear-to-color": [{ "mask-linear-to": F() }],
        "mask-image-t-from-pos": [{ "mask-t-from": z() }],
        "mask-image-t-to-pos": [{ "mask-t-to": z() }],
        "mask-image-t-from-color": [{ "mask-t-from": F() }],
        "mask-image-t-to-color": [{ "mask-t-to": F() }],
        "mask-image-r-from-pos": [{ "mask-r-from": z() }],
        "mask-image-r-to-pos": [{ "mask-r-to": z() }],
        "mask-image-r-from-color": [{ "mask-r-from": F() }],
        "mask-image-r-to-color": [{ "mask-r-to": F() }],
        "mask-image-b-from-pos": [{ "mask-b-from": z() }],
        "mask-image-b-to-pos": [{ "mask-b-to": z() }],
        "mask-image-b-from-color": [{ "mask-b-from": F() }],
        "mask-image-b-to-color": [{ "mask-b-to": F() }],
        "mask-image-l-from-pos": [{ "mask-l-from": z() }],
        "mask-image-l-to-pos": [{ "mask-l-to": z() }],
        "mask-image-l-from-color": [{ "mask-l-from": F() }],
        "mask-image-l-to-color": [{ "mask-l-to": F() }],
        "mask-image-x-from-pos": [{ "mask-x-from": z() }],
        "mask-image-x-to-pos": [{ "mask-x-to": z() }],
        "mask-image-x-from-color": [{ "mask-x-from": F() }],
        "mask-image-x-to-color": [{ "mask-x-to": F() }],
        "mask-image-y-from-pos": [{ "mask-y-from": z() }],
        "mask-image-y-to-pos": [{ "mask-y-to": z() }],
        "mask-image-y-from-color": [{ "mask-y-from": F() }],
        "mask-image-y-to-color": [{ "mask-y-to": F() }],
        "mask-image-radial": [{ "mask-radial": [X, J] }],
        "mask-image-radial-from-pos": [{ "mask-radial-from": z() }],
        "mask-image-radial-to-pos": [{ "mask-radial-to": z() }],
        "mask-image-radial-from-color": [{ "mask-radial-from": F() }],
        "mask-image-radial-to-color": [{ "mask-radial-to": F() }],
        "mask-image-radial-shape": [{ "mask-radial": [`circle`, `ellipse`] }],
        "mask-image-radial-size": [{ "mask-radial": [{ closest: [`side`, `corner`], farthest: [`side`, `corner`] }] }],
        "mask-image-radial-pos": [{ "mask-radial-at": b() }],
        "mask-image-conic-pos": [{ "mask-conic": [G] }],
        "mask-image-conic-from-pos": [{ "mask-conic-from": z() }],
        "mask-image-conic-to-pos": [{ "mask-conic-to": z() }],
        "mask-image-conic-from-color": [{ "mask-conic-from": F() }],
        "mask-image-conic-to-color": [{ "mask-conic-to": F() }],
        "mask-mode": [{ mask: [`alpha`, `luminance`, `match`] }],
        "mask-origin": [{ "mask-origin": [`border`, `padding`, `content`, `fill`, `stroke`, `view`] }],
        "mask-position": [{ mask: te() }],
        "mask-repeat": [{ mask: ne() }],
        "mask-size": [{ mask: re() }],
        "mask-type": [{ "mask-type": [`alpha`, `luminance`] }],
        "mask-image": [{ mask: [`none`, X, J] }],
        filter: [{ filter: [``, `none`, X, J] }],
        blur: [{ blur: oe() }],
        brightness: [{ brightness: [G, X, J] }],
        contrast: [{ contrast: [G, X, J] }],
        "drop-shadow": [{ "drop-shadow": [``, `none`, p, rt, Ze] }],
        "drop-shadow-color": [{ "drop-shadow": F() }],
        grayscale: [{ grayscale: [``, G, X, J] }],
        "hue-rotate": [{ "hue-rotate": [G, X, J] }],
        invert: [{ invert: [``, G, X, J] }],
        saturate: [{ saturate: [G, X, J] }],
        sepia: [{ sepia: [``, G, X, J] }],
        "backdrop-filter": [{ "backdrop-filter": [``, `none`, X, J] }],
        "backdrop-blur": [{ "backdrop-blur": oe() }],
        "backdrop-brightness": [{ "backdrop-brightness": [G, X, J] }],
        "backdrop-contrast": [{ "backdrop-contrast": [G, X, J] }],
        "backdrop-grayscale": [{ "backdrop-grayscale": [``, G, X, J] }],
        "backdrop-hue-rotate": [{ "backdrop-hue-rotate": [G, X, J] }],
        "backdrop-invert": [{ "backdrop-invert": [``, G, X, J] }],
        "backdrop-opacity": [{ "backdrop-opacity": [G, X, J] }],
        "backdrop-saturate": [{ "backdrop-saturate": [G, X, J] }],
        "backdrop-sepia": [{ "backdrop-sepia": [``, G, X, J] }],
        "border-collapse": [{ border: [`collapse`, `separate`] }],
        "border-spacing": [{ "border-spacing": w() }],
        "border-spacing-x": [{ "border-spacing-x": w() }],
        "border-spacing-y": [{ "border-spacing-y": w() }],
        "table-layout": [{ table: [`auto`, `fixed`] }],
        caption: [{ caption: [`top`, `bottom`] }],
        transition: [{ transition: [``, `all`, `colors`, `opacity`, `shadow`, `transform`, `none`, X, J] }],
        "transition-behavior": [{ transition: [`normal`, `discrete`] }],
        duration: [{ duration: [G, `initial`, X, J] }],
        ease: [{ ease: [`linear`, `initial`, _, X, J] }],
        delay: [{ delay: [G, X, J] }],
        animate: [{ animate: [`none`, v, X, J] }],
        backface: [{ backface: [`hidden`, `visible`] }],
        perspective: [{ perspective: [h, X, J] }],
        "perspective-origin": [{ "perspective-origin": x() }],
        rotate: [{ rotate: B() }],
        "rotate-x": [{ "rotate-x": B() }],
        "rotate-y": [{ "rotate-y": B() }],
        "rotate-z": [{ "rotate-z": B() }],
        scale: [{ scale: V() }],
        "scale-x": [{ "scale-x": V() }],
        "scale-y": [{ "scale-y": V() }],
        "scale-z": [{ "scale-z": V() }],
        "scale-3d": [`scale-3d`],
        skew: [{ skew: se() }],
        "skew-x": [{ "skew-x": se() }],
        "skew-y": [{ "skew-y": se() }],
        transform: [{ transform: [X, J, ``, `none`, `gpu`, `cpu`] }],
        "transform-origin": [{ origin: x() }],
        "transform-style": [{ transform: [`3d`, `flat`] }],
        translate: [{ translate: H() }],
        "translate-x": [{ "translate-x": H() }],
        "translate-y": [{ "translate-y": H() }],
        "translate-z": [{ "translate-z": H() }],
        "translate-none": [`translate-none`],
        zoom: [{ zoom: [K, X, J] }],
        accent: [{ accent: F() }],
        appearance: [{ appearance: [`none`, `auto`] }],
        "caret-color": [{ caret: F() }],
        "color-scheme": [{ scheme: [`normal`, `dark`, `light`, `light-dark`, `only-dark`, `only-light`] }],
        cursor: [
          {
            cursor: [
              `auto`,
              `default`,
              `pointer`,
              `wait`,
              `text`,
              `move`,
              `help`,
              `not-allowed`,
              `none`,
              `context-menu`,
              `progress`,
              `cell`,
              `crosshair`,
              `vertical-text`,
              `alias`,
              `copy`,
              `no-drop`,
              `grab`,
              `grabbing`,
              `all-scroll`,
              `col-resize`,
              `row-resize`,
              `n-resize`,
              `e-resize`,
              `s-resize`,
              `w-resize`,
              `ne-resize`,
              `nw-resize`,
              `se-resize`,
              `sw-resize`,
              `ew-resize`,
              `ns-resize`,
              `nesw-resize`,
              `nwse-resize`,
              `zoom-in`,
              `zoom-out`,
              X,
              J,
            ],
          },
        ],
        "field-sizing": [{ "field-sizing": [`fixed`, `content`] }],
        "pointer-events": [{ "pointer-events": [`auto`, `none`] }],
        resize: [{ resize: [`none`, ``, `y`, `x`] }],
        "scroll-behavior": [{ scroll: [`auto`, `smooth`] }],
        "scrollbar-thumb-color": [{ "scrollbar-thumb": F() }],
        "scrollbar-track-color": [{ "scrollbar-track": F() }],
        "scrollbar-gutter": [{ "scrollbar-gutter": [`auto`, `stable`, `both`] }],
        "scrollbar-w": [{ scrollbar: [`auto`, `thin`, `none`] }],
        "scroll-m": [{ "scroll-m": w() }],
        "scroll-mx": [{ "scroll-mx": w() }],
        "scroll-my": [{ "scroll-my": w() }],
        "scroll-ms": [{ "scroll-ms": w() }],
        "scroll-me": [{ "scroll-me": w() }],
        "scroll-mbs": [{ "scroll-mbs": w() }],
        "scroll-mbe": [{ "scroll-mbe": w() }],
        "scroll-mt": [{ "scroll-mt": w() }],
        "scroll-mr": [{ "scroll-mr": w() }],
        "scroll-mb": [{ "scroll-mb": w() }],
        "scroll-ml": [{ "scroll-ml": w() }],
        "scroll-p": [{ "scroll-p": w() }],
        "scroll-px": [{ "scroll-px": w() }],
        "scroll-py": [{ "scroll-py": w() }],
        "scroll-ps": [{ "scroll-ps": w() }],
        "scroll-pe": [{ "scroll-pe": w() }],
        "scroll-pbs": [{ "scroll-pbs": w() }],
        "scroll-pbe": [{ "scroll-pbe": w() }],
        "scroll-pt": [{ "scroll-pt": w() }],
        "scroll-pr": [{ "scroll-pr": w() }],
        "scroll-pb": [{ "scroll-pb": w() }],
        "scroll-pl": [{ "scroll-pl": w() }],
        "snap-align": [{ snap: [`start`, `end`, `center`, `align-none`] }],
        "snap-stop": [{ snap: [`normal`, `always`] }],
        "snap-type": [{ snap: [`none`, `x`, `y`, `both`] }],
        "snap-strictness": [{ snap: [`mandatory`, `proximity`] }],
        touch: [{ touch: [`auto`, `none`, `manipulation`] }],
        "touch-x": [{ "touch-pan": [`x`, `left`, `right`] }],
        "touch-y": [{ "touch-pan": [`y`, `up`, `down`] }],
        "touch-pz": [`touch-pinch-zoom`],
        select: [{ select: [`none`, `text`, `all`, `auto`] }],
        "will-change": [{ "will-change": [`auto`, `scroll`, `contents`, `transform`, X, J] }],
        fill: [{ fill: [`none`, ...F()] }],
        "stroke-w": [{ stroke: [G, Qe, Y, Ke] }],
        stroke: [{ stroke: [`none`, ...F()] }],
        "forced-color-adjust": [{ "forced-color-adjust": [`auto`, `none`] }],
      },
      conflictingClassGroups: {
        "container-named": [`container-type`],
        overflow: [`overflow-x`, `overflow-y`],
        overscroll: [`overscroll-x`, `overscroll-y`],
        inset: [`inset-x`, `inset-y`, `inset-bs`, `inset-be`, `start`, `end`, `top`, `right`, `bottom`, `left`],
        "inset-x": [`right`, `left`],
        "inset-y": [`top`, `bottom`],
        flex: [`basis`, `grow`, `shrink`],
        gap: [`gap-x`, `gap-y`],
        p: [`px`, `py`, `ps`, `pe`, `pbs`, `pbe`, `pt`, `pr`, `pb`, `pl`],
        px: [`pr`, `pl`],
        py: [`pt`, `pb`],
        m: [`mx`, `my`, `ms`, `me`, `mbs`, `mbe`, `mt`, `mr`, `mb`, `ml`],
        mx: [`mr`, `ml`],
        my: [`mt`, `mb`],
        size: [`w`, `h`],
        "font-size": [`leading`],
        "fvn-normal": [`fvn-ordinal`, `fvn-slashed-zero`, `fvn-figure`, `fvn-spacing`, `fvn-fraction`],
        "fvn-ordinal": [`fvn-normal`],
        "fvn-slashed-zero": [`fvn-normal`],
        "fvn-figure": [`fvn-normal`],
        "fvn-spacing": [`fvn-normal`],
        "fvn-fraction": [`fvn-normal`],
        "line-clamp": [`display`, `overflow`],
        rounded: [
          `rounded-s`,
          `rounded-e`,
          `rounded-t`,
          `rounded-r`,
          `rounded-b`,
          `rounded-l`,
          `rounded-ss`,
          `rounded-se`,
          `rounded-ee`,
          `rounded-es`,
          `rounded-tl`,
          `rounded-tr`,
          `rounded-br`,
          `rounded-bl`,
        ],
        "rounded-s": [`rounded-ss`, `rounded-es`],
        "rounded-e": [`rounded-se`, `rounded-ee`],
        "rounded-t": [`rounded-tl`, `rounded-tr`],
        "rounded-r": [`rounded-tr`, `rounded-br`],
        "rounded-b": [`rounded-br`, `rounded-bl`],
        "rounded-l": [`rounded-tl`, `rounded-bl`],
        "border-spacing": [`border-spacing-x`, `border-spacing-y`],
        "border-w": [
          `border-w-x`,
          `border-w-y`,
          `border-w-s`,
          `border-w-e`,
          `border-w-bs`,
          `border-w-be`,
          `border-w-t`,
          `border-w-r`,
          `border-w-b`,
          `border-w-l`,
        ],
        "border-w-x": [`border-w-r`, `border-w-l`],
        "border-w-y": [`border-w-t`, `border-w-b`],
        "border-color": [
          `border-color-x`,
          `border-color-y`,
          `border-color-s`,
          `border-color-e`,
          `border-color-bs`,
          `border-color-be`,
          `border-color-t`,
          `border-color-r`,
          `border-color-b`,
          `border-color-l`,
        ],
        "border-color-x": [`border-color-r`, `border-color-l`],
        "border-color-y": [`border-color-t`, `border-color-b`],
        translate: [`translate-x`, `translate-y`, `translate-none`],
        "translate-none": [`translate`, `translate-x`, `translate-y`, `translate-z`],
        "scroll-m": [
          `scroll-mx`,
          `scroll-my`,
          `scroll-ms`,
          `scroll-me`,
          `scroll-mbs`,
          `scroll-mbe`,
          `scroll-mt`,
          `scroll-mr`,
          `scroll-mb`,
          `scroll-ml`,
        ],
        "scroll-mx": [`scroll-mr`, `scroll-ml`],
        "scroll-my": [`scroll-mt`, `scroll-mb`],
        "scroll-p": [
          `scroll-px`,
          `scroll-py`,
          `scroll-ps`,
          `scroll-pe`,
          `scroll-pbs`,
          `scroll-pbe`,
          `scroll-pt`,
          `scroll-pr`,
          `scroll-pb`,
          `scroll-pl`,
        ],
        "scroll-px": [`scroll-pr`, `scroll-pl`],
        "scroll-py": [`scroll-pt`, `scroll-pb`],
        touch: [`touch-x`, `touch-y`, `touch-pz`],
        "touch-x": [`touch`],
        "touch-y": [`touch`],
        "touch-pz": [`touch`],
      },
      conflictingClassGroupModifiers: { "font-size": [`leading`] },
      postfixLookupClassGroups: [`container-type`],
      orderSensitiveModifiers: [
        `*`,
        `**`,
        `after`,
        `backdrop`,
        `before`,
        `details-content`,
        `file`,
        `first-letter`,
        `first-line`,
        `marker`,
        `placeholder`,
        `selection`,
      ],
    };
  });
function $(...e) {
  return pt(ne(e));
}
var mt = {
    success: `bg-success-soft text-success border-success/30`,
    warning: `bg-warning-soft text-warning border-warning/30`,
    danger: `bg-danger-soft text-danger border-danger/30`,
    info: `bg-info-soft text-info border-info/30`,
    neutral: `bg-neutral-soft text-neutral border-neutral/25`,
    sim: `bg-sim-soft text-sim border-sim/30`,
  },
  ht = { success: O, warning: F, danger: k, info: N, neutral: A, sim: M };
function gt(e) {
  let t = e.toLowerCase();
  return /(revoked|failed|error|absent(?!.*recovery)|blocked|overdue)/.test(t)
    ? `danger`
    : /(pending|partial|held|stale|review|awaiting|warning|forming|quota|interrupted|not yet|alert|open)/.test(t)
      ? `warning`
      : /(unavailable|not configured|not released|disabled|restricted|superseded|not submitted|not started|none|—)/.test(t)
        ? `neutral`
        : /(simulated|demo|prototype|sample)/.test(t)
          ? `sim`
          : /(issued|released|present|delivered|reviewed|saved|active|ready|approved|running|verified|submitted|available|completed|activated)/.test(
                t,
              )
            ? `success`
            : `info`;
}
function _t({ children: e, tone: t, className: n }) {
  let r = t ?? gt(String(e)),
    i = ht[r];
  return (0, m.jsxs)(`span`, {
    className: $(`inline-flex max-w-full items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-medium leading-5`, mt[r], n),
    children: [
      (0, m.jsx)(i, { className: `size-3.5 shrink-0`, "aria-hidden": !0 }),
      (0, m.jsx)(`span`, { className: `break-words`, children: e }),
    ],
  });
}
function vt({ children: e, className: t, title: n, action: r, id: i }) {
  return (0, m.jsxs)(`section`, {
    id: i,
    className: $(`rounded-xl border bg-card p-4 shadow-sm sm:p-5`, t),
    children: [
      (n || r) &&
        (0, m.jsxs)(`div`, {
          className: `mb-3 flex flex-wrap items-start justify-between gap-2`,
          children: [n && (0, m.jsx)(`h2`, { className: `text-base font-semibold text-foreground`, children: n }), r],
        }),
      e,
    ],
  });
}
function yt({ title: e, subtitle: t, children: n, source: r }) {
  return (0, m.jsxs)(`header`, {
    className: `mb-5 flex flex-wrap items-end justify-between gap-3`,
    children: [
      (0, m.jsxs)(`div`, {
        className: `min-w-0`,
        children: [
          (0, m.jsx)(`h1`, { className: `text-2xl font-semibold tracking-tight text-foreground`, children: e }),
          t && (0, m.jsx)(`p`, { className: `mt-1 text-sm text-muted-foreground`, children: t }),
          r &&
            (0, m.jsxs)(`p`, {
              className: `mt-1 text-xs text-muted-foreground`,
              children: [`Source: `, r, ` · Last successful update: 26 Sep 2026, 09:45 IST (sample)`],
            }),
        ],
      }),
      n && (0, m.jsx)(`div`, { className: `flex flex-wrap gap-2`, children: n }),
    ],
  });
}
function bt({ label: e, value: t, hint: n, rank: r, tone: i }) {
  return (0, m.jsxs)(`div`, {
    className: `rounded-xl border bg-card p-4 shadow-sm`,
    children: [
      (0, m.jsxs)(`div`, {
        className: `flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground`,
        children: [
          r &&
            (0, m.jsx)(`span`, {
              className: `grid size-5 place-items-center rounded-full bg-navy text-[11px] text-navy-foreground`,
              "aria-label": `Priority ${r}`,
              children: r,
            }),
          e,
        ],
      }),
      (0, m.jsx)(`div`, { className: `mt-2 text-xl font-semibold text-foreground`, children: t }),
      n && (0, m.jsx)(`div`, { className: `mt-1 text-sm text-muted-foreground`, children: n }),
      i &&
        (0, m.jsx)(`div`, {
          className: `mt-2`,
          children: (0, m.jsx)(_t, { tone: i, children: i === `neutral` ? `Unavailable` : i === `warning` ? `Attention` : `OK` }),
        }),
    ],
  });
}
function xt({ value: e, label: t }) {
  return e === null
    ? (0, m.jsxs)(`div`, {
        className: `text-sm`,
        children: [
          (0, m.jsxs)(`span`, { className: `font-medium`, children: [t, `: `] }),
          (0, m.jsx)(_t, { tone: `neutral`, children: `Not Configured / Unavailable` }),
        ],
      })
    : (0, m.jsxs)(`div`, {
        children: [
          (0, m.jsxs)(`div`, {
            className: `mb-1 flex justify-between text-sm`,
            children: [(0, m.jsx)(`span`, { children: t }), (0, m.jsxs)(`span`, { className: `font-medium`, children: [e, `%`] })],
          }),
          (0, m.jsx)(`div`, {
            className: `h-2.5 rounded-full bg-muted`,
            role: `progressbar`,
            "aria-valuenow": e,
            "aria-valuemin": 0,
            "aria-valuemax": 100,
            "aria-label": t,
            children: (0, m.jsx)(`div`, { className: `h-full rounded-full bg-primary`, style: { width: `${e}%` } }),
          }),
        ],
      });
}
function St({ items: e }) {
  return (0, m.jsx)(`dl`, {
    className: `grid gap-x-6 gap-y-2 sm:grid-cols-2`,
    children: e.map(([e, t], n) =>
      (0, m.jsxs)(
        `div`,
        {
          className: `min-w-0 border-b border-dashed pb-2`,
          children: [
            (0, m.jsx)(`dt`, { className: `text-xs text-muted-foreground`, children: e }),
            (0, m.jsx)(`dd`, { className: `break-words text-sm font-medium`, children: t }),
          ],
        },
        n,
      ),
    ),
  });
}
var Ct = {
  Loading: { tone: `info`, icon: P, text: `Loading sample data…` },
  Empty: { tone: `neutral`, icon: N, text: `Nothing here yet.` },
  "Partial Data": { tone: `warning`, icon: F, text: `Some sources did not respond; figures shown are incomplete.` },
  "Pending Verification": { tone: `warning`, icon: A, text: `Awaiting verification — not treated as confirmed.` },
  Stale: { tone: `warning`, icon: A, text: `Data is older than the freshness window.` },
  "Integration Unavailable": { tone: `neutral`, icon: j, text: `No live integration in this prototype.` },
  "Permission Restricted": { tone: `neutral`, icon: ee, text: `Your role cannot view this information.` },
  Error: { tone: `danger`, icon: k, text: `Something went wrong. Try again or raise a support request.` },
  Saving: { tone: `info`, icon: P, text: `Saving…` },
  Saved: { tone: `success`, icon: O, text: `Saved locally in this prototype.` },
  "Not Submitted": { tone: `neutral`, icon: N, text: `Not submitted yet.` },
  Failed: { tone: `danger`, icon: k, text: `Action failed.` },
  "Confirmation Pending": { tone: `warning`, icon: A, text: `Waiting for confirmation.` },
};
function wt({ state: e, children: t }) {
  let n = Ct[e],
    r = n.icon;
  return (0, m.jsxs)(`div`, {
    role: `status`,
    className: $(`flex items-start gap-2 rounded-lg border px-3 py-2 text-sm`, mt[n.tone]),
    children: [
      (0, m.jsx)(r, { className: $(`mt-0.5 size-4 shrink-0`, (e === `Loading` || e === `Saving`) && `animate-spin`), "aria-hidden": !0 }),
      (0, m.jsxs)(`div`, { children: [(0, m.jsxs)(`strong`, { className: `font-semibold`, children: [e, `:`] }), ` `, t ?? n.text] }),
    ],
  });
}
Object.keys(Ct);
function Tt({ children: e, message: t, variant: n = `primary`, className: r }) {
  let { notify: i } = y();
  return (0, m.jsxs)(Et, {
    variant: n,
    className: r,
    onClick: () => i(`Simulated only: ${t} No live service was contacted.`),
    children: [
      e,
      (0, m.jsx)(`span`, { className: `rounded bg-sim-soft px-1.5 text-[10px] font-semibold uppercase text-sim`, children: `Demo` }),
    ],
  });
}
function Et({ children: e, variant: t = `primary`, className: n, ...r }) {
  let i = {
    primary: `bg-primary text-primary-foreground hover:bg-primary/90`,
    outline: `border border-input bg-card text-foreground hover:bg-accent`,
    ghost: `text-foreground hover:bg-accent`,
  }[t];
  return (0, m.jsx)(`button`, {
    type: `button`,
    ...r,
    className: $(
      `tap inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors disabled:opacity-50`,
      i,
      n,
    ),
    children: e,
  });
}
function Dt({ rows: e, cols: t, caption: n, getKey: r }) {
  return (0, m.jsxs)(`div`, {
    children: [
      (0, m.jsx)(`div`, {
        className: `hidden overflow-x-auto rounded-xl border bg-card md:block`,
        children: (0, m.jsxs)(`table`, {
          className: `w-full text-left text-sm`,
          children: [
            (0, m.jsx)(`caption`, { className: `sr-only`, children: n }),
            (0, m.jsx)(`thead`, {
              className: `bg-muted text-xs uppercase tracking-wide text-muted-foreground`,
              children: (0, m.jsx)(`tr`, {
                children: t.map((e) => (0, m.jsx)(`th`, { scope: `col`, className: `px-3 py-2.5 font-semibold`, children: e.h }, e.h)),
              }),
            }),
            (0, m.jsx)(`tbody`, {
              children: e.map((e, n) =>
                (0, m.jsx)(
                  `tr`,
                  {
                    className: `border-t align-top`,
                    children: t.map((t) => (0, m.jsx)(`td`, { className: `px-3 py-2.5`, children: t.c(e) }, t.h)),
                  },
                  r(e, n),
                ),
              ),
            }),
          ],
        }),
      }),
      (0, m.jsx)(`ul`, {
        className: `space-y-3 md:hidden`,
        "aria-label": n,
        children: e.map((e, n) =>
          (0, m.jsx)(
            `li`,
            {
              className: `rounded-xl border bg-card p-3 shadow-sm`,
              children: (0, m.jsx)(`dl`, {
                className: `space-y-1.5`,
                children: t.map((t) =>
                  (0, m.jsxs)(
                    `div`,
                    {
                      className: `flex flex-wrap gap-x-2 text-sm`,
                      children: [
                        (0, m.jsx)(`dt`, { className: `min-w-24 text-xs text-muted-foreground`, children: t.h }),
                        (0, m.jsx)(`dd`, { className: `min-w-0 flex-1 break-words`, children: t.c(e) }),
                      ],
                    },
                    t.h,
                  ),
                ),
              }),
            },
            r(e, n),
          ),
        ),
      }),
    ],
  });
}
function Ot({ tabs: e, value: t, onChange: n, label: r }) {
  return (0, m.jsx)(`div`, {
    role: `tablist`,
    "aria-label": r,
    className: `mb-4 flex flex-wrap gap-2`,
    children: e.map((e) =>
      (0, m.jsx)(
        `button`,
        {
          role: `tab`,
          "aria-selected": t === e,
          onClick: () => n(e),
          className: $(
            `tap rounded-full border px-4 py-1.5 text-sm font-medium`,
            t === e ? `border-primary bg-primary text-primary-foreground` : `bg-card hover:bg-accent`,
          ),
          children: e,
        },
        e,
      ),
    ),
  });
}
function kt({ children: e, cols: t = 3 }) {
  let n = { 2: `md:grid-cols-2`, 3: `md:grid-cols-2 lg:grid-cols-3`, 4: `sm:grid-cols-2 lg:grid-cols-4` }[t];
  return (0, m.jsx)(`div`, { className: $(`grid gap-4`, n), children: e });
}
function At({ children: e }) {
  return (0, m.jsxs)(`p`, {
    className: `rounded-lg border border-dashed bg-muted px-3 py-2 text-xs text-muted-foreground`,
    children: [(0, m.jsx)(N, { className: `mr-1 inline size-3.5`, "aria-hidden": !0 }), e],
  });
}
export {
  o as C,
  u as S,
  v as _,
  Dt as a,
  y as b,
  yt as c,
  bt as d,
  wt as f,
  D as g,
  M as h,
  vt as i,
  xt as l,
  $ as m,
  _t as n,
  kt as o,
  Ot as p,
  Et as r,
  St as s,
  At as t,
  Tt as u,
  h as v,
  c as w,
  f as x,
  g as y,
};
