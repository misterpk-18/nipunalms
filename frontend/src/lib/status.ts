/**
 * The one status dictionary. Every status the app shows comes from here: a fixed tone, a plain label and one line of help
 * ("what it means / what to do"). Screens never pick a colour from the text of a status; they name a domain and a code.
 *
 * `label` is what people read, `tkey` (optional) is the translation key for student screens, `help` is the tooltip.
 * A code the dictionary does not know shows its own text in a neutral tone and warns in development, so a new status
 * from the API is visible at once without breaking the screen.
 */
import type { TranslationKey } from "@/lib/i18n";

export type StatusTone = "success" | "warning" | "danger" | "info" | "neutral";
export type StatusInfo = { label: string; tone: StatusTone; help: string; tkey?: TranslationKey };

const s = (label: string, tone: StatusTone, help: string, tkey?: TranslationKey): StatusInfo => (tkey ? { label, tone, help, tkey } : { label, tone, help });

export const STATUS = {
  /** A student's course enrolment. */
  enrolment: {
    "Provisioning Pending": s("Access being set up", "warning", "Course content opens once the qualifying payment is verified."),
    "Allocation Pending": s("Waiting for a batch", "info", "The course is confirmed. The branch will give you a batch before your first class."),
    "Allocated — awaiting first regular class": s("Batch allocated", "info", "You have a batch. Your Joining Date is set when you attend your first regular class."),
    Active: s("In progress", "success", "You are learning in this course."),
    Paused: s("Paused", "warning", "The course is paused. Ask your branch to resume it."),
    Completed: s("Completed", "success", "You have completed this course."),
    Withdrawn: s("Withdrawn", "neutral", "This enrolment has ended."),
  },
  /** A student's seat in a batch. */
  seat: {
    Active: s("Seated", "success", "Holds a seat in the batch."),
    Ended: s("Ended", "neutral", "The seat ended."),
    Transferred: s("Moved", "neutral", "Moved to another batch."),
  },
  /** A batch's lifecycle state (the label the API sends). */
  batch: {
    Draft: s("Draft", "neutral", "Not proposed yet. Finish the readiness points, then propose it."),
    Proposed: s("Proposed", "warning", "Waiting to be confirmed."),
    Confirmed: s("Confirmed", "info", "Confirmed: it can take students and will start on its date."),
    "In Progress": s("In progress", "success", "Classes are running."),
    "In Progress (Full)": s("In progress, full", "success", "Classes are running and every seat is taken."),
    "On Hold": s("On hold", "warning", "Paused. It takes no new students until it is resumed."),
    Completed: s("Completed", "success", "The batch has finished."),
    Cancelled: s("Cancelled", "danger", "The batch was cancelled."),
    Archived: s("Archived", "neutral", "Finished and closed."),
  },
  /** Whether a batch can start. */
  readiness: {
    Ready: s("Ready", "success", "Everything needed to start is in place."),
    Blocked: s("Blocked", "danger", "Something stops this batch from starting. See the reason and fix it."),
    "Pending Verification": s("Waiting for a check", "warning", "A check is still open, for example the Meet organizer."),
  },
  /** A class session's label. */
  session: {
    Planned: s("Planned", "neutral", "Scheduled but not confirmed yet."),
    Confirmed: s("Confirmed", "info", "Confirmed and ready."),
    Scheduled: s("Scheduled", "info", "Scheduled."),
    "Not scheduled": s("Not scheduled", "neutral", "No class is scheduled for this yet."),
    "In delivery": s("Being taught", "info", "Classes for this are under way."),
    Live: s("Live", "success", "The class is on now."),
    "In Progress": s("In progress", "success", "The class is on now."),
    Held: s("Held", "success", "The class took place."),
    Delivered: s("Held", "success", "The class took place."),
    "Partially Held": s("Partly held", "warning", "Only part of the class was delivered. A replacement may be owed."),
    "Not Held": s("Not held", "danger", "The class did not take place."),
    Cancelled: s("Cancelled", "danger", "The class was cancelled."),
    Rescheduled: s("Moved", "warning", "The class was moved to another time."),
    Locked: s("Locked", "neutral", "No more changes without a correction request."),
  },
  /** The Meet link of a class. */
  meet: {
    "Not Required": s("No link needed", "neutral", "This class is not online."),
    "Pending Verification": s("Link not ready", "warning", "The Meet link is not verified yet."),
    Associated: s("Link ready", "success", "The Meet link is set."),
    Linked: s("Link ready", "success", "The Meet link is set."),
    Failed: s("Link failed", "danger", "The Meet link did not work. Set a new one."),
    Unavailable: s("No link", "danger", "There is no working Meet link."),
  },
  /** One student's attendance entry, and the register's state. */
  attendance: {
    Present: s("Present", "success", "Marked present."),
    Absent: s("Absent", "danger", "Marked absent. You can ask for a recovery."),
    Late: s("Late", "warning", "Joined late."),
    Excused: s("Excused", "info", "Absence excused."),
    "Not yet marked": s("Not yet marked", "warning", "Nobody has marked this class yet."),
    "Partially marked": s("Partly marked", "warning", "Some students are still unmarked."),
    Marked: s("Marked", "success", "Every seat is marked."),
    "No seats": s("No students", "neutral", "No student holds a seat in this class."),
    "Not started": s("Not started", "neutral", "No class has been held yet."),
    "Partial Data": s("Incomplete data", "warning", "Some sources did not respond, so the figure is incomplete."),
    Calculated: s("Calculated", "success", "Calculated from the records."),
  },
  /** An assignment as its author sees it. */
  assignment: {
    Draft: s("Draft", "neutral", "Not released to students yet."),
    Released: s("Released", "success", "Students can see it and submit."),
    Withdrawn: s("Withdrawn", "neutral", "Taken back. Students no longer see it."),
  },
  /** A student's work item (assignment submission). */
  work: {
    Upcoming: s("Upcoming", "neutral", "Not due yet."),
    Due: s("Due soon", "warning", "Due in the next few days."),
    Overdue: s("Overdue", "danger", "The deadline has passed."),
    Submitted: s("Submitted", "info", "Handed in and waiting for review."),
    "Under Review": s("Being reviewed", "info", "Your trainer is reviewing it."),
    Reviewed: s("Reviewed", "success", "Your trainer has reviewed it."),
    "Resubmission Requested": s("Resubmit", "warning", "Your trainer asked for another version."),
  },
  /** A test as the author or the student sees it. */
  test: {
    "Configuration Pending": s("Setting up", "warning", "Something is still missing before it can be released."),
    "Not Released": s("Not released", "neutral", "Ready, but students cannot see it yet."),
    Released: s("Open", "success", "Students can take it in its window."),
    Closed: s("Closed", "neutral", "The window has ended."),
    Available: s("Open", "success", "Students can take it in its window."),
    Scheduled: s("Scheduled", "info", "Opens at the scheduled time."),
    "In progress": s("In progress", "info", "An attempt is under way."),
    Pending: s("Pending", "warning", "Waiting."),
    "Awaiting Grading": s("To grade", "warning", "Answers wait for a trainer to mark them."),
    Graded: s("Marked", "success", "Marked."),
  },
  /** A result. */
  result: {
    Provisional: s("Provisional", "warning", "Marks are not final until the Branch Manager publishes them."),
    Moderated: s("Moderated", "info", "Checked and waiting to be published."),
    Published: s("Published", "success", "Final marks are visible to students."),
    Pass: s("Pass", "success", "Passed."),
    Fail: s("Not passed", "danger", "Below the pass mark."),
    "Not attempted": s("Not attempted", "neutral", "No attempt yet."),
  },
  /** A certificate register entry. */
  certificate: {
    "Not Yet Eligible": s("Not yet eligible", "neutral", "The course is not completed yet."),
    "Eligibility Review": s("In review", "warning", "Completed. The Branch Manager is reviewing it."),
    "Awaiting Approval": s("Awaiting approval", "warning", "Recommended and waiting for approval."),
    "Approved for Issue": s("Approved", "info", "Approved. It will be issued next."),
    Issued: s("Issued", "success", "Issued. It can be verified publicly."),
    Superseded: s("Replaced", "neutral", "A corrected version replaced this one."),
    Revoked: s("Revoked", "danger", "Withdrawn. It no longer verifies as valid."),
    Cleared: s("Fee cleared", "success", "The fee is paid."),
    Outstanding: s("Fee outstanding", "danger", "The fee is not paid. The certificate waits for it."),
    "Not Received": s("Fee status unknown", "warning", "The fee status has not arrived from the CRM."),
    "Released by exception": s("Fee released", "info", "Released by an approved exception."),
    "Valid — Current Version": s("Valid", "success", "This is the current valid certificate."),
  },
  /** A support request. */
  support: {
    Open: s("Open", "warning", "Waiting for a reply."),
    "In Progress": s("In progress", "info", "Being worked on."),
    "Waiting on Student": s("Waiting for you", "warning", "A reply from the student is needed."),
    Resolved: s("Resolved", "success", "Answered. It can be closed or reopened."),
    Closed: s("Closed", "neutral", "Closed."),
  },
  /** A content item in the library. */
  content: {
    Draft: s("Draft", "neutral", "Not sent for review yet."),
    Submitted: s("Waiting for review", "warning", "Sent to the Branch Manager for review."),
    "Under Review": s("Being reviewed", "info", "The Branch Manager is reviewing it."),
    Approved: s("Approved", "info", "Approved. It can be released."),
    Released: s("Released", "success", "Students can see it."),
    "Changes Requested": s("Changes requested", "warning", "The reviewer asked for changes. Edit and send it again."),
    Rejected: s("Rejected", "danger", "Not accepted."),
    Retired: s("Retired", "neutral", "No longer shown to students."),
  },
  /** A class recording, and a problem with one. */
  recording: {
    Processing: s("Being prepared", "info", "The recording is being prepared."),
    Released: s("Available", "success", "You can watch it."),
    Partial: s("Partly available", "warning", "Only part of the class was recorded."),
    Held: s("On hold", "warning", "Held for review. You will be told when it is available."),
    Unavailable: s("Not available", "neutral", "No recording is available for this class."),
    Expired: s("Access ended", "neutral", "Access to this recording has ended."),
    "Integration Unavailable": s("Drive not connected", "neutral", "Recording storage is not connected yet."),
    Open: s("Open", "warning", "Not handled yet."),
    "In Progress": s("In progress", "info", "Being handled."),
    Resolved: s("Resolved", "success", "Handled."),
  },
  /** A notification. */
  notification: {
    Delivered: s("Delivered", "success", "Delivered."),
    Failed: s("Not delivered", "neutral", "Could not be delivered on that channel."),
    Unread: s("New", "warning", "Not read yet."),
    Read: s("Read", "success", "Read."),
    Acknowledged: s("Acknowledged", "success", "Acknowledged."),
    None: s("No action", "neutral", "Nothing to do."),
    Open: s("Needs action", "warning", "Waiting for you."),
    Completed: s("Done", "success", "The action is complete."),
  },
  /** Career: a referral profile, an opportunity, an application, an outcome. */
  career: {
    "Not Ready": s("Not ready", "neutral", "Complete the steps before you can be referred."),
    "In Preparation": s("Getting ready", "warning", "Keep improving your profile and CV."),
    "Referral Ready": s("Ready for referral", "success", "You can be shared with employers."),
    "Verification Pending": s("Waiting to be verified", "warning", "A second person has to verify the employer."),
    Active: s("Open", "success", "Open for applications."),
    "On Hold": s("On hold", "warning", "Paused."),
    Closed: s("Closed", "neutral", "No longer taking applications."),
    Applied: s("Applied", "info", "Application sent."),
    Shortlisted: s("Shortlisted", "success", "Shortlisted by the employer."),
    "Interview Scheduled": s("Interview set", "info", "An interview is scheduled."),
    "Offer Received": s("Offer received", "success", "An offer arrived."),
    Rejected: s("Not selected", "danger", "Not selected."),
    Withdrawn: s("Withdrawn", "neutral", "Withdrawn."),
    "Pending Verification": s("Waiting to be confirmed", "warning", "A second person still has to confirm it."),
    Verified: s("Verified", "success", "Confirmed with evidence."),
  },
  /** A CV file's review. */
  cv: {
    "Not Reviewed": s("Not reviewed", "neutral", "Waiting for a review."),
    Reviewed: s("Reviewed", "success", "Reviewed."),
    "Changes Requested": s("Changes requested", "warning", "Update the CV and upload it again."),
  },
  /** A student's preferred-slot request. */
  slot: {
    Requested: s("Requested", "warning", "Sent. It reserves no seat."),
    Waitlisted: s("On the waiting list", "info", "We will tell you when a matching batch is proposed."),
    Confirmed: s("Confirmed", "success", "Confirmed."),
    "Not Possible": s("Not possible", "danger", "We cannot arrange this slot."),
    Withdrawn: s("Withdrawn", "neutral", "You withdrew this request."),
    Open: s("Open", "success", "Open for booking."),
    "Slot Confirmation Pending": s("Waiting for confirmation", "warning", "Waiting for the slot to be confirmed."),
    Cancelled: s("Cancelled", "danger", "Cancelled."),
    Completed: s("Done", "success", "Done."),
  },
  /** An integration's setup and check (Setup & health). */
  integration: {
    "Not Configured": s("Not set up", "neutral", "Not set up yet."),
    "Configuration Pending": s("Set-up pending", "warning", "Set-up is under way."),
    Configured: s("Set up", "info", "Set up, not yet checked."),
    Misconfigured: s("Set up wrongly", "danger", "The settings are wrong. Fix them."),
    "Not Verified": s("Not checked", "neutral", "Nobody has checked that it works."),
    "Pending Verification": s("Waiting for a check", "warning", "A check is still open."),
    Verified: s("Working", "success", "Checked and working."),
    Failed: s("Broken", "danger", "The check failed."),
    Unavailable: s("Not connected", "neutral", "This integration is not connected yet."),
    "Integration Unavailable": s("Not connected", "neutral", "This integration is not connected yet."),
    Off: s("Off", "neutral", "Switched off."),
    On: s("On", "success", "Switched on."),
  },
  /** CRM events received, and what the LMS sends back. */
  crmEvent: {
    Received: s("Received", "info", "Received and waiting to be applied."),
    Applied: s("Applied", "success", "Applied."),
    "Ignored — stale": s("Skipped (old)", "neutral", "A newer version was already applied."),
    Failed: s("Failed", "danger", "Could not be applied. Retry it or fix the cause."),
    Pending: s("Waiting", "warning", "Waiting to be picked up."),
    Delivered: s("Delivered", "success", "Delivered."),
  },
  /** A curriculum version. */
  curriculum: {
    Draft: s("Draft", "neutral", "Being written. Not final."),
    "Under Review": s("Under review", "warning", "Submitted and waiting for review."),
    Approved: s("Approved", "info", "Approved. It can be activated."),
    Active: s("Active", "success", "In use for new batches."),
    Retired: s("Retired", "neutral", "Replaced by a newer version."),
    Deleted: s("Deleted", "neutral", "Deleted."),
  },
  /** Anything that waits for someone to approve it (requests, closures, mappings, guests, cover, corrections). */
  approval: {
    Pending: s("Waiting for a decision", "warning", "Waiting for someone to decide."),
    "Pending Approval": s("Waiting for a decision", "warning", "Waiting for someone to decide."),
    "Awaiting Agreement": s("Waiting for students", "warning", "Students are being asked to agree."),
    Approved: s("Approved", "success", "Approved."),
    Applied: s("Done", "success", "Approved and applied."),
    Rejected: s("Rejected", "danger", "Not approved."),
    Declined: s("Declined", "danger", "Declined."),
    Withdrawn: s("Withdrawn", "neutral", "Withdrawn."),
    Open: s("Open", "warning", "Waiting to be handled."),
    Requested: s("Requested", "warning", "Asked for and waiting."),
    Waitlisted: s("On the waiting list", "info", "Waiting for a place."),
    Completed: s("Done", "success", "Done."),
    Resolved: s("Resolved", "success", "Handled."),
    Matched: s("Matched", "success", "Matched to a person."),
    Unmatched: s("Not matched", "warning", "No person matched. Review it."),
    Dismissed: s("Dismissed", "neutral", "Dismissed."),
  },
  /** The exception / recovery queue and recovery steps. */
  exception: {
    Open: s("Open", "warning", "Needs someone to take it."),
    "Recovery In Progress": s("Being worked on", "info", "A recovery step was logged."),
    Overdue: s("Overdue", "danger", "Past its deadline."),
    Failed: s("Failed", "danger", "Failed."),
    Escalated: s("Escalated", "danger", "Moved up because it was not handled in time."),
    "Pending Verification": s("Waiting for a check", "warning", "A check is still open."),
    "Awaiting Review": s("Waiting for review", "warning", "Waiting for review."),
    "Awaiting Approval": s("Waiting for a decision", "warning", "Waiting for a decision."),
    "Awaiting named owner": s("No owner yet", "warning", "Nobody owns this yet. Log a step to take it."),
  },
  /** A staff or student login. */
  account: {
    Active: s("Active", "success", "Can sign in."),
    Deactivated: s("Deactivated", "neutral", "Cannot sign in."),
    Locked: s("Locked", "danger", "Locked after failed sign-ins. Unlock it."),
    "Must change password": s("Must change password", "warning", "Has to set a new password at the next sign-in."),
    "Account Created": s("Account created", "info", "The login exists. No activation link was used yet."),
    "Activation Pending": s("Waiting to activate", "warning", "The activation link has not been used."),
    Activated: s("Activated", "success", "The student has activated the account."),
    Suspended: s("Suspended", "danger", "Cannot sign in until it is reactivated."),
  },
  /** Question bank. */
  question: {
    Draft: s("Draft", "neutral", "Waiting for approval before it can go in a test."),
    Approved: s("Approved", "success", "Can be used in tests."),
    Retired: s("Retired", "neutral", "No longer used."),
  },
  /** Completion review and the trainer's recommendation. */
  completion: {
    Open: s("Open", "warning", "Waiting for a decision."),
    Decided: s("Decided", "success", "Decided."),
    Complete: s("Complete", "success", "Complete."),
    "Not Yet": s("Not yet", "warning", "Not yet complete."),
    "Needs Recovery": s("Needs recovery", "danger", "Needs a recovery plan before it can complete."),
    "Review open": s("Review open", "warning", "A completion review is open."),
  },
  /** How fresh or complete a dashboard figure is. */
  figure: {
    Configured: s("Available", "success", "Figures are available."),
    "Partial Data": s("Incomplete data", "warning", "Some sources did not respond, so the figure is incomplete."),
    "Not Configured": s("Not connected", "neutral", "The source is not connected, so there is no figure."),
    Fresh: s("Up to date", "success", "Recent figures."),
    Stale: s("Out of date", "warning", "Older than the freshness window."),
    Empty: s("Nothing yet", "neutral", "No data yet."),
    Unavailable: s("Not available", "neutral", "Not available."),
    Ready: s("Ready", "success", "Ready."),
    "Configuration Pending": s("Not set up", "warning", "Set-up is pending."),
    "Awaiting Approval": s("Awaiting a decision", "warning", "Waiting for a decision."),
  },
  /** Ask Nipuna availability. */
  assistant: {
    "AI Available": s("Available", "success", "Ask Nipuna is on."),
    "Configuration Pending": s("Not set up", "warning", "The AI provider is not set up. Rule-based answers only."),
    "AI Unavailable": s("Not available", "danger", "Ask Nipuna is not available."),
    "Quota Limited": s("Daily limit reached", "warning", "The daily allowance is used up. It resets tomorrow."),
    Disabled: s("Switched off", "danger", "Ask Nipuna has been switched off."),
    Refused: s("Can't answer", "warning", "This is not something Ask Nipuna can answer."),
    Fallback: s("Rule-based answer", "neutral", "Answered from the records without AI."),
    Answered: s("Answered", "info", "Answered."),
  },
} as const satisfies Record<string, Record<string, StatusInfo>>;

export type StatusDomain = keyof typeof STATUS;

const warned = new Set<string>();

/** The label, tone and help of a status. Unknown codes show their own text, neutral, and warn once in development. */
export function statusInfo(domain: StatusDomain, code: string | number | null | undefined): StatusInfo {
  const key = code === null || code === undefined || code === "" ? "—" : String(code);
  const entry = (STATUS[domain] as Record<string, StatusInfo>)[key];
  if (entry) return entry;
  if (import.meta.env.DEV && key !== "—" && !warned.has(`${domain}:${key}`)) {
    warned.add(`${domain}:${key}`);
    console.warn(`[status] "${key}" is not in the ${domain} status dictionary (lib/status.ts)`);
  }
  return { label: key, tone: "neutral", help: "" };
}
