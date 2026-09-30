import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { deliveryApi } from "@/api/delivery";
import { PageHead, QueryView } from "@/components/lms/ui";
import { DeliveryBar } from "@/features/shared/delivery-ui";
import { ModuleList } from "./course-detail";

export function TrackDetail() {
  const { enrolmentId, trackId } = useParams({ strict: false }) as { enrolmentId: string; trackId: string };
  const query = useQuery({
    queryKey: ["delivery", "my-track", enrolmentId, trackId],
    queryFn: () => deliveryApi.myTrack(Number(enrolmentId), Number(trackId)),
  });
  return (
    <div className="mx-auto max-w-5xl">
      <QueryView query={query}>
        {({ enrolment, track, delivery, modules }) => (
          <>
            <nav aria-label="Breadcrumb" className="mb-2 text-sm">
              <Link to="/my-courses" className="text-primary underline">
                My Courses
              </Link>{" "}
              /{" "}
              <Link to="/courses/$enrolmentId" params={{ enrolmentId }} className="text-primary underline">
                {enrolment.course.course_code} (parent)
              </Link>{" "}
              / {track.track_code}
            </nav>
            <div className="mb-3 rounded-lg border bg-muted px-3 py-2 text-sm">
              <strong>Parent programme:</strong> {enrolment.course.course_code} — {enrolment.course.title} ·{" "}
              {enrolment.curriculum_version?.version_label ?? "Curriculum Mapping Pending"}
            </div>
            <PageHead
              title={track.track_name}
              description={`${track.track_code} · ${track.role} · ${track.curriculum_version?.version_label ?? "Curriculum Mapping Pending"}`}
            />
            <div className="mb-4">
              <DeliveryBar delivery={delivery} label="Track curriculum delivered" />
            </div>
            <ModuleList modules={modules} empty="No modules released for this track yet." />
          </>
        )}
      </QueryView>
    </div>
  );
}
