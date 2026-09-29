import { S as e, a as t, c as n, n as r, p as i, t as a, w as o, x as s } from "./ui-BRNtr3Vo.js";
var c = o(e(), 1),
  l = s(),
  u = [
    {
      id: `n1`,
      text: `Assignment 'Regression on housing dataset' due 29 Sep`,
      group: `Action Required`,
      delivery: `Delivered in-app`,
      read: `Unread`,
      ack: `Not acknowledged`,
      action: `Not completed`,
    },
    {
      id: `n2`,
      text: `Recording for 24 Sep held for review`,
      group: `My Notifications`,
      delivery: `Delivered in-app`,
      read: `Read`,
      ack: `Acknowledged`,
      action: `—`,
    },
    {
      id: `n3`,
      text: `WhatsApp reminder for class 28 Sep`,
      group: `System Issues`,
      delivery: `External channel — Pending Verification (not sent)`,
      read: `—`,
      ack: `—`,
      action: `—`,
    },
    {
      id: `n4`,
      text: `Support request SR-1019 resolved`,
      group: `Completed`,
      delivery: `Delivered in-app`,
      read: `Read`,
      ack: `Acknowledged`,
      action: `Action Completed`,
    },
    {
      id: `n5`,
      text: `Module test scheduled 03 Oct`,
      group: `My Notifications`,
      delivery: `Delivered in-app`,
      read: `Unread`,
      ack: `Not acknowledged`,
      action: `—`,
    },
  ],
  d = [`My Notifications`, `Action Required`, `Unread`, `Completed`, `System Issues`];
function f({ title: e }) {
  let [o, s] = (0, c.useState)(`My Notifications`),
    f = o === `Unread` ? u.filter((e) => e.read === `Unread`) : o === `My Notifications` ? u : u.filter((e) => e.group === o);
  return (0, l.jsxs)(`div`, {
    className: `mx-auto max-w-6xl`,
    children: [
      (0, l.jsx)(n, { title: e, subtitle: `In-app notification centre` }),
      (0, l.jsx)(i, { tabs: d, value: o, onChange: s, label: `Notification views` }),
      (0, l.jsx)(t, {
        caption: `Notifications`,
        rows: f,
        getKey: (e) => e.id,
        cols: [
          { h: `Notification`, c: (e) => e.text },
          { h: `Delivery`, c: (e) => (0, l.jsx)(r, { children: e.delivery }) },
          { h: `Read`, c: (e) => (0, l.jsx)(r, { children: e.read }) },
          { h: `Acknowledged`, c: (e) => (0, l.jsx)(r, { children: e.ack }) },
          { h: `Action`, c: (e) => (0, l.jsx)(r, { children: e.action }) },
        ],
      }),
      (0, l.jsx)(`div`, {
        className: `mt-4`,
        children: (0, l.jsx)(a, {
          children: `Delivery, Read, Acknowledged and Action Completed are tracked separately. No WhatsApp or email delivery is verified in this prototype.`,
        }),
      }),
    ],
  });
}
export { f as t };
