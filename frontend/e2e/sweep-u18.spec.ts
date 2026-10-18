import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { PASSWORD, USERS, login } from "./helpers";

/**
 * UX phase U18, the final sweep. Two parts:
 *  1. A crawl per role: every link in the role's navigation opens without a server error, with a heading, no leftover spec words
 *     and no horizontal scroll (phone), in light and dark mode; badges keep enough contrast in dark mode.
 *  2. Main jobs that no other spec walks end to end: the student joins a class and opens a recording, the Branch Manager's completion
 *     screen. (Adding staff and retrying a CRM update are in admin.spec.ts and admin-u17.spec.ts.)
 * Run against a freshly seeded database (see docs/DEVELOPMENT.md Part A).
 */

const RUN = Date.now().toString(36);
const LEFTOVER =
  /Module \d+|§|Pending Verification|Actual Class Session|Mapping Pending|CRM authoritative|[Oo]utbox|Recovery Owner|\bundefined\b|\bNaN\b|\[object Object\]/;

type Role = { name: string; login: string };
const ROLES: Role[] = [
  { name: "student", login: USERS.student },
  { name: "trainer", login: USERS.trainerG1 },
  { name: "branch manager", login: USERS.bmGnt },
  { name: "founder", login: USERS.founder },
  { name: "super admin", login: USERS.admin },
];

async function navLinks(page: Page): Promise<string[]> {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  const nav = page.getByRole("navigation", { name: "Main" });
  await expect(nav.getByRole("link").first()).toBeVisible();
  const hrefs = await nav.getByRole("link").evaluateAll((els) => els.map((e) => (e as HTMLAnchorElement).getAttribute("href") ?? ""));
  return [...new Set(hrefs.filter((h) => h.startsWith("/")))];
}

/** Opens each path and returns what went wrong, one line per problem. */
async function crawl(page: Page, paths: string[], opts: { phone?: boolean } = {}): Promise<string[]> {
  const problems: string[] = [];
  let current = "";
  page.on("response", (r) => {
    const url = r.url();
    if (url.includes("/api/") && r.status() >= 500) problems.push(`${current}: ${r.status()} ${url}`);
  });
  page.on("pageerror", (e) => problems.push(`${current}: script error ${e.message}`));
  for (const path of paths) {
    current = path;
    await page.goto(path);
    try {
      await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
    } catch {
      problems.push(`${path}: no heading`);
      continue;
    }
    await page.waitForLoadState("networkidle").catch(() => undefined);
    if (await page.getByText(/could not be loaded|Something went wrong/i).count()) problems.push(`${path}: shows an error card`);
    const text = await page.locator("main").innerText();
    // the Setup & health notes for the two Meet organizers are written by migrations 001 / 060 (history, not edited)
    const hit = (path.endsWith("/setup") ? text.replace(/Pending Verification/g, "") : text).match(LEFTOVER);
    if (hit) problems.push(`${path}: leftover wording "${hit[0]}"`);
    if (opts.phone) {
      const over = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
      if (over > 1) problems.push(`${path}: scrolls sideways by ${over}px`);
    }
  }
  return problems;
}

/** Badge text against its own background (over the page) in the current colour scheme; returns badges under 4.5:1. */
async function lowContrastBadges(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 1;
    const ctx = canvas.getContext("2d", { willReadFrequently: true })!;
    const rgba = (css: string): [number, number, number, number] => {
      ctx.clearRect(0, 0, 1, 1);
      ctx.fillStyle = "#000";
      ctx.fillStyle = css;
      ctx.fillRect(0, 0, 1, 1);
      const d = ctx.getImageData(0, 0, 1, 1).data;
      return [d[0]!, d[1]!, d[2]!, d[3]! / 255];
    };
    const over = (top: number[], below: number[]) => [0, 1, 2].map((i) => top[i]! * top[3]! + below[i]! * (1 - top[3]!));
    const lum = (c: number[]) => {
      const f = (v: number) => ((v /= 255) <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
      return 0.2126 * f(c[0]!) + 0.7152 * f(c[1]!) + 0.0722 * f(c[2]!);
    };
    const backdrop = (el: Element): number[] => {
      let acc: number[] = [255, 255, 255, 1];
      const chain: Element[] = [];
      for (let e: Element | null = el; e; e = e.parentElement) chain.unshift(e);
      for (const e of chain) {
        const bg = rgba(getComputedStyle(e).backgroundColor);
        if (bg[3] > 0) acc = [...over(bg, acc), 1];
      }
      return acc;
    };
    const out: string[] = [];
    const seen = new Set<string>();
    for (const el of Array.from(document.querySelectorAll("main span, main div"))) {
      const cls = el.getAttribute("class") ?? "";
      if (!/\bbg-(success|warning|danger|info|neutral)-soft\b/.test(cls)) continue;
      const text = (el.textContent ?? "").trim();
      if (!text || seen.has(cls + text)) continue;
      seen.add(cls + text);
      const bg = backdrop(el);
      const fg = over(rgba(getComputedStyle(el).color), bg);
      const [a, b] = [lum(fg), lum(bg)];
      const ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
      if (ratio < 4.5) out.push(`${text.slice(0, 40)} (${ratio.toFixed(2)}:1)`);
    }
    return out;
  });
}

test.describe("each role's navigation, light and dark", () => {
  test.describe.configure({ mode: "serial" });
  for (const role of ROLES) {
    test(`${role.name}: every nav link opens clean, light then dark`, async ({ page }, info) => {
      test.skip(info.project.name === "mobile", "desktop crawl; the phone crawl is below");
      test.setTimeout(240_000);
      await page.emulateMedia({ colorScheme: "light" });
      await login(page, role.login);
      const links = await navLinks(page);
      expect(links.length, "nav links").toBeGreaterThan(3);
      const light = await crawl(page, links);
      expect(light, light.join("\n")).toEqual([]);

      await page.emulateMedia({ colorScheme: "dark" });
      const dark: string[] = [];
      for (const path of links) {
        await page.goto(path);
        await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
        await page.waitForLoadState("networkidle").catch(() => undefined);
        const bodyBg = await page.evaluate(() => getComputedStyle(document.body).backgroundColor);
        if (bodyBg === "rgb(255, 255, 255)") dark.push(`${path}: body stays white in dark mode`);
        for (const b of await lowContrastBadges(page)) dark.push(`${path}: badge ${b}`);
        // exactly one nav item is marked as the current page (the Founder once highlighted two), and it is visibly different from the rest
        const active = page.getByRole("navigation", { name: "Main" }).locator('a[aria-current="page"]');
        if ((await active.count()) !== 1) dark.push(`${path}: ${await active.count()} active nav items`);
        else {
          const [color, bg] = await active.evaluate((e) => [getComputedStyle(e).color, getComputedStyle(e).backgroundColor]);
          if (color === bg || bg === "rgba(0, 0, 0, 0)") dark.push(`${path}: active nav item is not highlighted`);
        }
      }
      expect(dark, dark.join("\n")).toEqual([]);
    });
  }
});

test.describe("each role at phone width @mobile", () => {
  test.describe.configure({ mode: "serial" });
  for (const role of ROLES) {
    test(`${role.name}: every nav screen fits the phone @mobile`, async ({ page }) => {
      test.setTimeout(240_000);
      await login(page, role.login);
      const links = await navLinks(page);
      await page.setViewportSize({ width: 390, height: 844 });
      const problems = await crawl(page, links, { phone: true });
      expect(problems, problems.join("\n")).toEqual([]);
    });
  }
});

// ---------------------------------------------------------------- main jobs

async function apiLogin(request: APIRequestContext, loginId: string) {
  const response = await request.post("/api/v1/auth/login", { data: { login: loginId, password: PASSWORD } });
  expect(response.ok()).toBeTruthy();
  const { data } = await response.json();
  return data.token as string;
}
const auth = (token: string) => ({ Authorization: `Bearer ${token}` });

test.describe("main jobs", () => {
  test.describe.configure({ mode: "serial" });

  test("student: a class starting soon shows Join once the Meet link is saved, and a recording opens", async ({ page, request }, info) => {
    test.skip(info.project.name === "mobile", "desktop flow");
    const nowIst = new Date(Date.now() + 5.5 * 3600_000);
    test.skip(nowIst.getUTCHours() >= 23, "too close to midnight IST for a class today");
    const bm = await apiLogin(request, USERS.bmGnt);
    const student = await apiLogin(request, USERS.student);
    const mine = await (await request.get("/api/v1/me/schedule", { headers: auth(student) })).json();
    const batchId = (mine.data?.upcoming?.[0] ?? mine.data?.sessions?.[0] ?? mine.data?.[0])?.batch_id as number | undefined;
    const batches = await (await request.get("/api/v1/batches", { headers: auth(bm) })).json();
    const useBatch = batchId ?? (batches.data[0].batch_id as number);
    const start = new Date(Date.now() + 9 * 60_000);
    const created = await request.post("/api/v1/class-sessions", {
      headers: auth(bm),
      data: {
        batch_id: useBatch,
        title: `Sweep join ${RUN}`,
        starts_at: start.toISOString(),
        ends_at: new Date(start.getTime() + 30 * 60_000).toISOString(),
        mode: "Live Online",
        override_reason: "sweep",
      },
    });
    test.skip(created.status() !== 201, `a class could not be added (${created.status()}): ${(await created.text()).slice(0, 120)}`);
    const sessionId = (await created.json()).data[0].session_id as number;

    await login(page, USERS.student);
    await page.goto("/schedule");
    const card = page.getByRole("listitem").filter({ hasText: `Sweep join ${RUN}` });
    await expect(card).toBeVisible();
    await expect(card.getByRole("button", { name: "Join class" })).toBeDisabled(); // no Meet link yet, and it says why
    await expect(card).toContainText("Meet link");

    const saved = await request.put(`/api/v1/class-sessions/${sessionId}/meet`, {
      headers: auth(bm),
      data: { meet_link: `https://meet.google.com/swp-${RUN}-abc` },
    });
    expect(saved.ok(), await saved.text()).toBeTruthy();
    await page.reload();
    const join = page
      .getByRole("listitem")
      .filter({ hasText: `Sweep join ${RUN}` })
      .getByRole("link", { name: /^Join/ });
    await expect(join).toBeVisible();
    await expect(join).toHaveAttribute("href", /meet\.google\.com/);

    // a recording: Class Materials lists it, and Watch opens it
    await page.goto("/materials");
    await expect(page.getByRole("heading", { level: 1, name: "Class Materials" })).toBeVisible();
    const watch = page
      .getByRole("button", { name: "Watch" })
      .or(page.getByRole("link", { name: "Watch" }))
      .first();
    await expect(watch).toBeVisible();
    await watch.click();
    await expect(page.getByRole("dialog").or(page.locator("video, iframe")).first()).toBeVisible();
  });

  test("branch manager: a trainer recommends, the Branch Manager decides Complete with a confirm, and the certificate moves to review", async ({
    page,
    request,
  }, info) => {
    test.skip(info.project.name === "mobile", "desktop flow");
    const bm = await apiLogin(request, USERS.bmGnt);
    const rows = await (await request.get("/api/v1/progress/students?per_page=100", { headers: auth(bm) })).json();
    const row = rows.data.find(
      (r: { student: { full_name: string }; enrolment: { status: string } }) => r.student.full_name === "Sample Learner G." && r.enrolment.status === "Active",
    );
    expect(row, "Sample Learner G. has an Active enrolment").toBeTruthy();
    const enrolmentId = row.enrolment.enrolment_id as number;
    const opened = await request.post("/api/v1/completion-reviews", { headers: auth(bm), data: { enrolment_id: enrolmentId } });
    expect(opened.ok(), await opened.text()).toBeTruthy();
    const reviewId = (await opened.json()).data.review_id as number;
    let recommended = false;
    for (const trainer of [USERS.trainerG1, "trainer.g2@nipuna.test", "trainer.g3@nipuna.test"]) {
      const token = await apiLogin(request, trainer);
      const r = await request.post(`/api/v1/completion-reviews/${reviewId}/recommendation`, {
        headers: auth(token),
        data: { recommendation: "Complete", comment: "Ready" },
      });
      if (r.ok()) {
        recommended = true;
        break;
      }
    }
    expect(recommended, "a trainer of the batch recommends Complete").toBeTruthy();

    await login(page, USERS.bmGnt);
    await page.goto("/branch/completion");
    const item = page.getByRole("listitem").filter({ hasText: "Sample Learner G." });
    await expect(item).toBeVisible();
    await item.getByRole("button", { name: "Decide" }).click();
    const dialog = page.getByRole("dialog");
    await expect(dialog.getByRole("button", { name: "Continue" })).toBeDisabled(); // nothing is chosen for you
    await dialog.getByLabel(/^Complete/).check();
    await dialog.getByRole("button", { name: "Continue" }).click();
    const confirm = page.getByRole("alertdialog");
    await expect(confirm).toContainText("certificate moves to review");
    await confirm.getByRole("button", { name: "Mark complete" }).click();
    await expect(page.getByText("Sample Learner G. is marked complete")).toBeVisible();
    // with the fee not cleared the certificate waits for the fee, otherwise it goes to review
    await page.getByRole("tab", { name: /^Waiting for fee/ }).click();
    await expect(page.locator("main").getByRole("listitem").filter({ hasText: "Sample Learner G." })).toBeVisible();
  });
});
