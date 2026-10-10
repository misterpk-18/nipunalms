import { Fragment } from "react";
import { Link } from "@tanstack/react-router";
import { Breadcrumb, BreadcrumbItem, BreadcrumbList, BreadcrumbPage, BreadcrumbSeparator } from "@/components/ui/breadcrumb";

export type Crumb = { label: string; to?: string };

/** Where you are: links for the levels above, plain text for this page. Detail pages use it instead of a back button. */
export function Breadcrumbs({ items }: { items: Crumb[] }) {
  return (
    <Breadcrumb className="mb-2">
      <BreadcrumbList>
        {items.map((item, i) => (
          <Fragment key={`${item.label}-${i}`}>
            {i > 0 && <BreadcrumbSeparator />}
            <BreadcrumbItem>
              {item.to && i < items.length - 1 ? (
                <Link to={item.to} className="text-primary underline-offset-2 hover:underline">
                  {item.label}
                </Link>
              ) : (
                <BreadcrumbPage>{item.label}</BreadcrumbPage>
              )}
            </BreadcrumbItem>
          </Fragment>
        ))}
      </BreadcrumbList>
    </Breadcrumb>
  );
}
