import { a as e, c as t, n, t as r, u as i, x as a } from "./ui-BRNtr3Vo.js";
import { x as o } from "./index-BqZ61Way.js";
var s = a(),
  c = [
    { id: `r1`, title: `Regression notes`, type: `PDF`, used: `Track 2 · Regression; Booster · Forecasting`, access: `Until 12 Jan 2027` },
    { id: `r2`, title: `housing.csv`, type: `Dataset`, used: `Track 2 · Regression`, access: `Until 12 Jan 2027` },
    { id: `r3`, title: `SQL window functions cheatsheet`, type: `Notes`, used: `Track 1 · SQL`, access: `Until 12 Jan 2027` },
    { id: `r4`, title: `starter_tree.py`, type: `Code file`, used: `Track 2 · Trees`, access: `Until 12 Jan 2027` },
    { id: `r5`, title: `AWS lab guide`, type: `Lab file`, used: `NIT-CRS-007`, access: `Pending — no Joining Date` },
    { id: `r6`, title: `scikit-learn docs`, type: `Link`, used: `Track 2`, access: `External link` },
    {
      id: `r7`,
      title: `Recording ref: Window functions lab`,
      type: `Recording reference`,
      used: `Track 1 · SQL`,
      access: `Until 12 Jan 2027`,
    },
    { id: `r8`, title: `Assignment ref: Regression`, type: `Assignment reference`, used: `Track 2`, access: `Until 12 Jan 2027` },
    { id: `r9`, title: `Practice set 3`, type: `Practice material`, used: `Track 2`, access: `Until 12 Jan 2027` },
  ];
function l() {
  let a = o();
  return (0, s.jsxs)(`div`, {
    className: `mx-auto max-w-6xl`,
    children: [
      (0, s.jsx)(t, { title: a(`resources`), subtitle: `Content Library`, source: `LMS content register` }),
      (0, s.jsx)(`p`, {
        className: `mb-4 text-sm`,
        children: `Learning materials follow the same default: one year from Joining Date, plus one requested extension to the second anniversary, unless accepted course/offer/corporate/licence terms differ.`,
      }),
      (0, s.jsx)(e, {
        caption: `Resources`,
        rows: c,
        getKey: (e) => e.id,
        cols: [
          { h: `Resource`, c: (e) => (0, s.jsx)(`span`, { className: `font-medium`, children: e.title }) },
          { h: `Type`, c: (e) => (0, s.jsx)(n, { tone: `info`, children: e.type }) },
          { h: `Used in`, c: (e) => e.used },
          { h: `Access`, c: (e) => e.access },
          { h: `Open`, c: () => (0, s.jsx)(i, { variant: `outline`, message: `File would open from LMS storage.`, children: `Open` }) },
        ],
      }),
      (0, s.jsx)(`div`, {
        className: `mt-4`,
        children: (0, s.jsx)(r, {
          children: `One authoritative resource can appear in multiple placements; progress and files are not duplicated.`,
        }),
      }),
    ],
  });
}
export { l as component };
