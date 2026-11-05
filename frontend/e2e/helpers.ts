import { expect, type APIRequestContext, type Page } from "@playwright/test";

export const PASSWORD = "Nipuna-staging-1";

/** Staging accounts (all use PASSWORD). The student signs in with the Student ID; staff with their email. */
export const USERS = {
  student: "NIT-STU-2026-004182",
  founder: "founder@nipuna.test",
  admin: "admin@nipuna.test",
  bmGnt: "bm.gnt@nipuna.test",
  bmVij: "bm.vij@nipuna.test",
  // a Branch Manager of both branches: picks one after sign-in (the staging seed adds this account)
  bmMulti: "bm.multi@nipuna.test",
  // The Academic Coordinator role was merged into the Branch Manager (db 106): these keep the specs that used to sign in as one
  coordGnt: "bm.gnt@nipuna.test",
  coordVij: "bm.vij@nipuna.test",
  trainerG1: "trainer.g1@nipuna.test",
  trainerV1: "trainer.v1@nipuna.test",
} as const;

export async function login(page: Page, loginId: string, password = PASSWORD) {
  // Stay on a /login?redirect=… page the app already sent us to, so the redirect is kept
  if (!new URL(page.url()).pathname.startsWith("/login")) await page.goto("/login");
  await page.getByLabel("Student ID or email", { exact: true }).fill(loginId);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).not.toHaveURL(/\/login/);
}

/**
 * An upcoming class for Trainer R. Sample's Guntur batch (NIT-GNT-BAT-2026-000001), `daysAhead` days from now, 10:00–12:00 IST,
 * created by the Guntur Branch Manager. The staging classes sit in Sep–Oct 2026, so a test that needs a class still to come makes one.
 */
export async function createUpcomingClass(request: APIRequestContext, title: string, daysAhead = 3) {
  const login = await request.post("/api/v1/auth/login", { data: { login: USERS.bmGnt, password: PASSWORD } });
  const headers = { Authorization: `Bearer ${(await login.json()).data.token}` };
  const batches = (await (await request.get("/api/v1/batches?per_page=100", { headers })).json()).data as { batch_id: number; batch_code: string }[];
  const batch = batches.find((b) => b.batch_code === "NIT-GNT-BAT-2026-000001")!;
  const day = new Date(Date.now() + daysAhead * 86_400_000).toISOString().slice(0, 10);
  const made = await request.post("/api/v1/class-sessions", {
    headers,
    data: { batch_id: batch.batch_id, title, starts_at: `${day}T10:00:00+05:30`, ends_at: `${day}T12:00:00+05:30` },
  });
  expect(made.status(), await made.text()).toBe(201);
}
