import { createFileRoute } from "@tanstack/react-router";

/** `/` never renders: the root guard sends signed-in users to their `home_route` and everyone else to /login. */
export const Route = createFileRoute("/")({ component: () => null });
