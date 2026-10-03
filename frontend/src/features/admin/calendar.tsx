import { PageHead, Section } from "@/components/lms/ui";
import { AcademicCalendar } from "@/features/shared/academic-calendar";

export function AdminCalendar() {
  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <PageHead
        title="Academic Calendar"
        description="Company holidays and branch closures. Working-day targets (allocation, attendance confirmation, reviews) skip these dates."
      />
      <Section>
        <AcademicCalendar />
      </Section>
    </div>
  );
}
