import { createFileRoute, redirect } from "@tanstack/react-router";

/** Attendance & progress was renamed Attendance: the URL now matches the label. Old links, bookmarks and notifications keep working. */
export const Route = createFileRoute("/branch/progress")({
  beforeLoad: ({ location }) => {
    throw redirect({ href: `/branch/attendance${location.searchStr}`, replace: true });
  },
});
