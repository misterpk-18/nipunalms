/**
 * The two cross-branch staff areas (Super Admin under `/admin`, Founder under `/founder`). The Founder does everything the Super
 * Admin does (decision 16), so both areas are editable; the route picks the area and the screen never reads the role itself.
 */
export type CentralArea = { base: "/admin" | "/founder"; canEdit: boolean };

export const ADMIN_AREA: CentralArea = { base: "/admin", canEdit: true };
export const FOUNDER_AREA: CentralArea = { base: "/founder", canEdit: true };

/** A route path inside the area, for a typed `Link`/`navigate` (`areaTo(area, "/students/$id")`). */
export const areaTo = (area: CentralArea, path: string) => `${area.base}${path}` as never;

/** Props for a typed `Link` to a route inside the area, with its path params: `<Link {...areaLink(area, "/students/$id", { id })}>`. */
export const areaLink = (area: CentralArea, path: string, params?: Record<string, string>) => ({
  to: areaTo(area, path),
  ...(params ? { params: params as never } : {}),
});
