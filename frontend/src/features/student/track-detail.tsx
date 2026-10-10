import { useQuery } from "@tanstack/react-query";
import { useParams } from "@tanstack/react-router";
import { Breadcrumbs } from "@/components/lms/breadcrumbs";
import { deliveryApi } from "@/api/delivery";
import { PageHead, QueryView } from "@/components/lms/ui";
import { useT } from "@/lib/i18n";
import { ModuleList } from "./course-detail";

export function TrackDetail() {
  const t = useT();
  const { enrolmentId, trackId } = useParams({ strict: false }) as { enrolmentId: string; trackId: string };
  const query = useQuery({
    queryKey: ["delivery", "my-track", enrolmentId, trackId],
    queryFn: () => deliveryApi.myTrack(Number(enrolmentId), Number(trackId)),
  });
  return (
    <div className="mx-auto max-w-5xl">
      <QueryView query={query}>
        {({ enrolment, track, modules }) => (
          <>
            <Breadcrumbs
              items={[
                { label: t("breadcrumbMyLearning"), to: "/my-courses" },
                { label: enrolment.course.course_code, to: `/courses/${enrolmentId}` },
                { label: track.track_name },
              ]}
            />
            <PageHead title={track.track_name} description={`${enrolment.course.title} · ${track.role}`} />
            <ModuleList modules={modules} empty={t("noModulesYet")} />
          </>
        )}
      </QueryView>
    </div>
  );
}
