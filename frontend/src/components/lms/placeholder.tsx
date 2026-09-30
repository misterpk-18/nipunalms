import { PageHead, StatusNote } from "./ui";

/** Temporary body for routes whose slice is not built yet; the slice replaces the feature component that renders it. */
export function Placeholder({ title, description }: { title: string; description: string }) {
  return (
    <>
      <PageHead title={title} description={description} />
      <StatusNote state="Empty">This screen is being built.</StatusNote>
    </>
  );
}
