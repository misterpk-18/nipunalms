import { expect, type Page } from "@playwright/test";

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
