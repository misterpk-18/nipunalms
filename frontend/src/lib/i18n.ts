/**
 * EN / తెలుగు labels. Only student-facing text is translated (like the approved prototype); staff workspaces stay
 * in English. The chosen language is remembered per user in localStorage and defaults to the student's
 * `preferred_language`.
 */
import { useCallback, useEffect, useSyncExternalStore } from "react";
import type { Language } from "@/api/types";
import { useAuth } from "@/auth/auth";

const DICTIONARY = {
  home: ["Home", "హోమ్"],
  myLearning: ["My Learning", "నా అభ్యాసం"],
  myCourses: ["My Courses", "నా కోర్సులు"],
  schedule: ["Schedule", "షెడ్యూల్"],
  tasks: ["Tasks", "పనులు"],
  more: ["More", "మరిన్ని"],
  gettingStarted: ["Getting started", "ప్రారంభించండి"],
  dismiss: ["Dismiss", "మూసివేయండి"],
  go: ["Go", "వెళ్ళండి"],
  stepActivate: ["Activate your account", "మీ ఖాతాను యాక్టివేట్ చేయండి"],
  stepBatch: ["Check your batch", "మీ బ్యాచ్‌ను చూడండి"],
  stepClass: ["Join your first class", "మొదటి తరగతిలో చేరండి"],
  stepTask: ["Submit your first task", "మొదటి పనిని సమర్పించండి"],
  recordings: ["Recordings", "రికార్డింగ్‌లు"],
  resources: ["Resources", "వనరులు"],
  assignments: ["Assignments", "అసైన్‌మెంట్‌లు"],
  tests: ["Tests", "పరీక్షలు"],
  attendance: ["Attendance", "హాజరు"],
  progress: ["Progress", "పురోగతి"],
  results: ["Results", "ఫలితాలు"],
  certificates: ["Certificates", "సర్టిఫికెట్లు"],
  career: ["Career", "కెరీర్"],
  askNipuna: ["Ask Nipuna", "నిపుణను అడగండి"],
  support: ["Support", "సహాయం"],
  notifications: ["Notifications", "నోటిఫికేషన్లు"],
  finance: ["Fees & Receipts", "ఫీజులు & రసీదులు"],
  profile: ["Profile", "ప్రొఫైల్"],
  nextClass: ["Next Class", "తదుపరి తరగతి"],
  dueWork: ["Due Work", "గడువు పనులు"],
  courseProgress: ["Current Course Progress", "ప్రస్తుత కోర్సు పురోగతి"],
  continueLearning: ["Continue Learning", "అభ్యాసం కొనసాగించండి"],
  latestRecording: ["Latest Released Recording", "తాజా విడుదలైన రికార్డింగ్"],
  upcomingWork: ["Upcoming Assignment / Test", "రాబోయే అసైన్‌మెంట్ / పరీక్ష"],
  attendanceAlert: ["Attendance Alert", "హాజరు హెచ్చరిక"],
  certStatus: ["Certificate Status", "సర్టిఫికెట్ స్థితి"],
  careerSupport: ["Career Support", "కెరీర్ సహాయం"],
  joinClass: ["Join Class", "తరగతిలో చేరండి"],
  watch: ["Watch", "చూడండి"],
  submit: ["Submit", "సమర్పించండి"],
  login: ["Sign in", "సైన్ ఇన్"],
  loginId: ["Student ID or email", "విద్యార్థి ID లేదా ఇమెయిల్"],
  password: ["Password", "పాస్‌వర్డ్"],
  forgot: ["Forgot password?", "పాస్‌వర్డ్ మర్చిపోయారా?"],
  requiredField: ["This field is required.", "ఈ ఫీల్డ్ తప్పనిసరి."],
  pendingVerification: ["Pending Verification", "ధృవీకరణ పెండింగ్‌లో ఉంది"],
  notConfigured: ["Not Configured", "కాన్ఫిగర్ చేయలేదు"],
  viewAll: ["View all", "అన్నీ చూడండి"],
  raiseRequest: ["Raise a request", "అభ్యర్థన చేయండి"],
  language: ["Language", "భాష"],
  noGuarantee: ["Placement / career assistance only — no guaranteed placement.", "ప్లేస్‌మెంట్ / కెరీర్ సహాయం మాత్రమే — ఉద్యోగ హామీ లేదు."],
  // Sign-in and activation screens (added for the live app)
  showPassword: ["Show password", "పాస్‌వర్డ్ చూపించు"],
  hidePassword: ["Hide password", "పాస్‌వర్డ్ దాచు"],
  forgotHelp: ["Ask your Branch Manager to send you a new activation link.", "కొత్త యాక్టివేషన్ లింక్ కోసం మీ బ్రాంచ్ మేనేజర్‌ను అడగండి."],
  passwordPrivate: [
    "Staff can never see or set your password. Only you complete an activation or reset, through a verified link.",
    "సిబ్బంది మీ పాస్‌వర్డ్‌ను చూడలేరు లేదా సెట్ చేయలేరు. యాక్టివేషన్ లేదా రీసెట్ మీరు మాత్రమే ధృవీకరించిన లింక్ ద్వారా పూర్తి చేస్తారు.",
  ],
  oneLogin: ["Students have no CRM login. One LMS login per person across branches.", "విద్యార్థులకు CRM లాగిన్ లేదు. ఒక వ్యక్తికి ఒకే LMS లాగిన్."],
  activationStatus: ["Account activation status", "ఖాతా యాక్టివేషన్ స్థితి"],
  accountCreated: ["Account Created", "ఖాతా సృష్టించబడింది"],
  activationPending: ["Activation Pending", "యాక్టివేషన్ పెండింగ్"],
  activated: ["Activated", "యాక్టివేట్ అయింది"],
  courseAccessReleased: ["Course Access Released", "కోర్సు యాక్సెస్ విడుదలైంది"],
  accessAfterAllocation: ["Course access is released after academic batch allocation.", "బ్యాచ్ కేటాయింపు తర్వాత కోర్సు యాక్సెస్ విడుదల అవుతుంది."],
  activateAccount: ["Activate your account", "మీ ఖాతాను యాక్టివేట్ చేయండి"],
  newPassword: ["New password", "కొత్త పాస్‌వర్డ్"],
  confirmPassword: ["Confirm password", "పాస్‌వర్డ్ నిర్ధారించండి"],
  passwordMismatch: ["Passwords don't match.", "పాస్‌వర్డ్‌లు సరిపోలడం లేదు."],
  activateNow: ["Activate account", "ఖాతాను యాక్టివేట్ చేయండి"],
  goToSignIn: ["Go to sign in", "సైన్ ఇన్‌కు వెళ్లండి"],
  // Sign-in, reset and activation (UX phase U7)
  loginHelp: ["Students sign in with their Student ID, staff with their email.", "విద్యార్థులు Student ID తో, సిబ్బంది ఇమెయిల్‌తో సైన్ ఇన్ అవుతారు."],
  firstTime: ["First time here?", "మొదటిసారి వచ్చారా?"],
  activateLink: ["Activate your account", "మీ ఖాతాను యాక్టివేట్ చేయండి"],
  activateHelp: [
    "Open the activation link your branch sent you on WhatsApp. It works once. If you can't find it, ask your branch for a new one.",
    "మీ బ్రాంచ్ WhatsApp లో పంపిన యాక్టివేషన్ లింక్‌ను తెరవండి. అది ఒక్కసారి మాత్రమే పనిచేస్తుంది. కనబడకపోతే కొత్త లింక్ కోసం మీ బ్రాంచ్‌ను అడగండి.",
  ],
  resetTitle: ["Reset your password", "మీ పాస్‌వర్డ్‌ను రీసెట్ చేయండి"],
  resetAskHelp: [
    "Enter your Student ID or email. We'll send a 6-digit code to the WhatsApp number on file.",
    "మీ Student ID లేదా ఇమెయిల్ ఇవ్వండి. రికార్డులో ఉన్న WhatsApp నంబర్‌కు 6 అంకెల కోడ్ పంపుతాము.",
  ],
  sendCode: ["Send me a code", "కోడ్ పంపండి"],
  codeSent: ["If the account exists, we've sent a code.", "ఖాతా ఉంటే, మేము కోడ్ పంపాము."],
  codeHelp: [
    "The code works for 10 minutes. No message after a few minutes? Ask your branch to reset your password.",
    "కోడ్ 10 నిమిషాలు పనిచేస్తుంది. కొన్ని నిమిషాల తర్వాత సందేశం రాకపోతే, పాస్‌వర్డ్ రీసెట్ కోసం మీ బ్రాంచ్‌ను అడగండి.",
  ],
  codeLabel: ["6-digit code", "6 అంకెల కోడ్"],
  sendAgain: ["Send a new code", "కొత్త కోడ్ పంపండి"],
  setNewPassword: ["Save new password", "కొత్త పాస్‌వర్డ్‌ను సేవ్ చేయండి"],
  resetDone: ["Your password is changed. Sign in with the new one.", "మీ పాస్‌వర్డ్ మారింది. కొత్త దానితో సైన్ ఇన్ చేయండి."],
  backToSignIn: ["Back to sign in", "సైన్ ఇన్‌కు తిరిగి వెళ్ళండి"],
  ruleLength: ["At least {n} characters", "కనీసం {n} అక్షరాలు"],
  ruleMatch: ["Both passwords match", "రెండు పాస్‌వర్డ్‌లు సరిపోతున్నాయి"],
  ruleDiffers: ["Different from your current password", "ప్రస్తుత పాస్‌వర్డ్‌కు భిన్నంగా ఉంది"],
  linkExpired: ["This activation link has expired.", "ఈ యాక్టివేషన్ లింక్ గడువు ముగిసింది."],
  linkUsed: ["This activation link has already been used. Sign in instead.", "ఈ యాక్టివేషన్ లింక్ ఇప్పటికే వాడబడింది. బదులుగా సైన్ ఇన్ చేయండి."],
  linkReplaced: ["A newer link was sent to you. Use the newest message.", "మీకు కొత్త లింక్ పంపబడింది. తాజా సందేశాన్ని వాడండి."],
  linkNotFound: ["We can't find this activation link.", "ఈ యాక్టివేషన్ లింక్ కనబడలేదు."],
  linkAskBranch: ["Ask your branch for a new link.", "కొత్త లింక్ కోసం మీ బ్రాంచ్‌ను అడగండి."],
  chooseYourPassword: ["Choose your password", "మీ పాస్‌వర్డ్‌ను ఎంచుకోండి"],
  welcomeName: ["Welcome, {name}", "స్వాగతం, {name}"],
  allSet: ["Your account is ready", "మీ ఖాతా సిద్ధంగా ఉంది"],
  yourStudentId: ["Your Student ID", "మీ Student ID"],
  studentIdHelp: ["Use this ID to sign in next time. Keep it safe.", "తదుపరిసారి సైన్ ఇన్ కావడానికి ఈ ID వాడండి. భద్రంగా ఉంచుకోండి."],
  staffSignInHelp: ["You sign in with your email address.", "మీరు మీ ఇమెయిల్ చిరునామాతో సైన్ ఇన్ అవుతారు."],
  goToHome: ["Go to Home", "హోమ్‌కు వెళ్ళండి"],
  changePasswordTitle: ["Set a new password", "కొత్త పాస్‌వర్డ్‌ను సెట్ చేయండి"],
  changePasswordTemp: [
    "Your account has a temporary password. Choose a new one to continue.",
    "మీ ఖాతాకు తాత్కాలిక పాస్‌వర్డ్ ఉంది. కొనసాగడానికి కొత్తది ఎంచుకోండి.",
  ],
  changePasswordIntro: ["Change your password.", "మీ పాస్‌వర్డ్‌ను మార్చండి."],
  currentPassword: ["Current password", "ప్రస్తుత పాస్‌వర్డ్"],
  changePassword: ["Change password", "పాస్‌వర్డ్ మార్చండి"],
  passwordChanged: ["Password changed. Your other sessions were signed out.", "పాస్‌వర్డ్ మారింది. మీ ఇతర సెషన్‌లు సైన్ అవుట్ అయ్యాయి."],
  signOutInstead: ["Sign out instead", "బదులుగా సైన్ అవుట్ చేయండి"],
  cancel: ["Cancel", "రద్దు"],
  // Student Home and My Learning (UX phase U8)
  upNext: ["Up next", "తర్వాత చేయాల్సినది"],
  upNextLiveNow: ["Your class is on now", "మీ తరగతి ఇప్పుడు జరుగుతోంది"],
  upNextClassSoon: ["Your class is about to start", "మీ తరగతి త్వరలో మొదలవుతుంది"],
  upNextWorkDue: ["Work due today", "ఈ రోజు గడువు ఉన్న పని"],
  upNextWorkOverdue: ["Overdue work", "గడువు దాటిన పని"],
  upNextWorkMore: ["{n} things need you today", "ఈ రోజు {n} పనులు మీ కోసం ఉన్నాయి"],
  upNextContinue: ["Carry on with your next topic", "మీ తదుపరి అంశంతో కొనసాగండి"],
  upNextNextClass: ["Your next class", "మీ తదుపరి తరగతి"],
  upNextNothing: ["You are all caught up", "మీరు అన్నీ పూర్తి చేశారు"],
  upNextNothingHelp: [
    "Nothing needs you right now. New classes and work appear here as soon as your branch adds them.",
    "ప్రస్తుతం మీ కోసం ఏమీ లేదు. మీ బ్రాంచ్ కొత్త తరగతులు, పనులు జోడించగానే ఇక్కడ కనిపిస్తాయి.",
  ],
  openTask: ["Open the task", "పనిని తెరవండి"],
  openTest: ["Open the test", "పరీక్షను తెరవండి"],
  openTopic: ["Open topic", "అంశాన్ని తెరవండి"],
  viewClass: ["View class", "తరగతిని చూడండి"],
  dueAt: ["Due {when}", "గడువు {when}"],
  overdueSince: ["Overdue since {when}", "{when} నుండి గడువు దాటింది"],
  startsAt: ["Starts {when}", "{when} కి మొదలవుతుంది"],
  liveNow: ["Live now", "ఇప్పుడు జరుగుతోంది"],
  joinNotReady: ["The Join button opens 15 minutes before the class.", "తరగతికి 15 నిమిషాల ముందు Join బటన్ తెరుచుకుంటుంది."],
  recordingNone: ["No recording has been released yet.", "ఇంకా రికార్డింగ్ విడుదల కాలేదు."],
  watchNow: ["Watch", "చూడండి"],
  allRecordings: ["All recordings", "అన్ని రికార్డింగ్‌లు"],
  allWork: ["All tasks and tests", "అన్ని పనులు, పరీక్షలు"],
  nothingDue: ["Nothing is due right now.", "ప్రస్తుతం గడువు ఉన్నది ఏమీ లేదు."],
  openAssignments: ["{n} open assignments", "{n} తెరిచి ఉన్న అసైన్‌మెంట్‌లు"],
  openTests: ["{n} open tests", "{n} తెరిచి ఉన్న పరీక్షలు"],
  noClassYet: ["No class yet", "ఇంకా తరగతి లేదు"],
  attendanceOnTrack: ["Your attendance is on track.", "మీ హాజరు సరిగ్గా ఉంది."],
  attendanceLow: ["Your attendance is below {n}%.", "మీ హాజరు {n}% కంటే తక్కువగా ఉంది."],
  attendanceMissed: ["You missed the class on {when}.", "{when} నాటి తరగతికి మీరు హాజరు కాలేదు."],
  askRecovery: ["Ask for a make-up class", "మేకప్ తరగతి కోసం అడగండి"],
  seeAttendance: ["See attendance", "హాజరును చూడండి"],
  attendanceNotStarted: ["Attendance starts with your batch's first class.", "మీ బ్యాచ్ మొదటి తరగతితో హాజరు మొదలవుతుంది."],
  batchChangeTitle: ["Your branch proposes a change to your batch", "మీ బ్రాంచ్ మీ బ్యాచ్‌లో మార్పును ప్రతిపాదిస్తోంది"],
  batchNow: ["Now", "ఇప్పుడు"],
  batchProposed: ["Proposed", "ప్రతిపాదన"],
  batchWhy: ["Why", "కారణం"],
  batchReplyBy: ["Please answer by {when}. Nothing changes for you until you do.", "దయచేసి {when} లోపు జవాబు ఇవ్వండి. మీరు జవాబు ఇచ్చే వరకు మీకు ఏమీ మారదు."],
  agree: ["Agree", "అంగీకరిస్తున్నాను"],
  decline: ["Decline", "అంగీకరించను"],
  agreeTitle: ["Agree to this change?", "ఈ మార్పును అంగీకరిస్తారా?"],
  agreeConsequence: [
    "You agree to the proposed plan. Your branch will apply it once everyone has answered.",
    "ప్రతిపాదించిన ప్రణాళికను మీరు అంగీకరిస్తున్నారు. అందరూ జవాబు ఇచ్చాక మీ బ్రాంచ్ దాన్ని అమలు చేస్తుంది.",
  ],
  declineTitle: ["Decline this change?", "ఈ మార్పును తిరస్కరిస్తారా?"],
  declineConsequence: ["Your branch will arrange an alternative with you.", "మీ బ్రాంచ్ మీతో కలిసి ప్రత్యామ్నాయాన్ని ఏర్పాటు చేస్తుంది."],
  answerRecorded: ["Your answer is recorded.", "మీ జవాబు నమోదైంది."],
  preferredSlot: ["Waiting for a batch", "బ్యాచ్ కోసం వేచి ఉన్నారు"],
  preferredSlotHelp: [
    "Tell your branch which days and times suit you. This reserves no seat, but it helps them find the right batch.",
    "మీకు ఏ రోజులు, సమయాలు అనుకూలమో మీ బ్రాంచ్‌కు చెప్పండి. ఇది సీటును రిజర్వ్ చేయదు, కానీ సరైన బ్యాచ్‌ను కనుగొనడంలో సహాయపడుతుంది.",
  ],
  continueTopic: ["Continue: {title}", "కొనసాగించండి: {title}"],
  startCourse: ["Start: {title}", "ప్రారంభించండి: {title}"],
  courseDone: ["Every topic is done", "అన్ని అంశాలు పూర్తయ్యాయి"],
  openCourse: ["Open course", "కోర్సును తెరవండి"],
  topicsDone: ["{done} of {total} topics done", "{total} అంశాలలో {done} పూర్తయ్యాయి"],
  noTopicsYet: ["Topics appear once your course has an approved curriculum.", "మీ కోర్సుకు ఆమోదిత పాఠ్యప్రణాళిక వచ్చాక అంశాలు కనిపిస్తాయి."],
  noCurriculumYet: ["No approved curriculum yet", "ఇంకా ఆమోదిత పాఠ్యప్రణాళిక లేదు"],
  batchLabel: ["Batch", "బ్యాచ్"],
  notAllocated: ["Not allocated yet", "ఇంకా కేటాయించలేదు"],
  noEnrolments: ["You have no courses yet. Your branch adds them after admission.", "మీకు ఇంకా కోర్సులు లేవు. అడ్మిషన్ తర్వాత మీ బ్రాంచ్ వాటిని జోడిస్తుంది."],
  myLearningHelp: ["Your courses, how far you are in each, and where to carry on.", "మీ కోర్సులు, ప్రతి దానిలో మీరు ఎంత దూరం వచ్చారు, ఎక్కడ కొనసాగాలి."],
  modulesTitle: ["Modules", "మాడ్యూళ్ళు"],
  programmeModules: ["Programme modules", "ప్రోగ్రామ్ మాడ్యూళ్ళు"],
  tracksTitle: ["Tracks in your programme", "మీ ప్రోగ్రామ్‌లోని ట్రాక్‌లు"],
  openTrack: ["Open track", "ట్రాక్‌ను తెరవండి"],
  noModulesYet: [
    "No modules yet. They appear once your course has an approved curriculum.",
    "ఇంకా మాడ్యూళ్ళు లేవు. మీ కోర్సుకు ఆమోదిత పాఠ్యప్రణాళిక వచ్చాక కనిపిస్తాయి.",
  ],
  topicsCount: ["{n} topics", "{n} అంశాలు"],
  comingUp: ["Coming up", "త్వరలో"],
  courseInfo: ["Course info", "కోర్సు సమాచారం"],
  courseInfoHelp: ["Your branch, batch, trainers and fee summary.", "మీ బ్రాంచ్, బ్యాచ్, ట్రైనర్లు, ఫీజు వివరాలు."],
  serviceBranch: ["Branch", "బ్రాంచ్"],
  trainersLabel: ["Trainers", "ట్రైనర్లు"],
  notAssigned: ["Not assigned yet", "ఇంకా కేటాయించలేదు"],
  deliveryMode: ["How you attend", "మీరు ఎలా హాజరవుతారు"],
  joiningDate: ["Joining date", "చేరిన తేదీ"],
  joiningPending: ["Set when you attend your first class", "మీ మొదటి తరగతికి హాజరైనప్పుడు నిర్ణయమవుతుంది"],
  accessUntil: ["Recordings and files until", "రికార్డింగ్‌లు, ఫైళ్ళు అందుబాటులో ఉండేది"],
  accessPending: ["Starts from your joining date", "మీ చేరిన తేదీ నుండి మొదలవుతుంది"],
  certificateLabel: ["Certificate", "సర్టిఫికెట్"],
  feeSummary: ["Fees", "ఫీజులు"],
  feeLine: ["Fee ₹{total} · Paid ₹{paid} · Due ₹{due}", "ఫీజు ₹{total} · చెల్లించింది ₹{paid} · బకాయి ₹{due}"],
  feesAndReceipts: ["Fees & receipts", "ఫీజులు & రసీదులు"],
  classesDelivered: ["Classes held", "జరిగిన తరగతులు"],
  noClassesPlanned: ["No classes planned yet", "ఇంకా తరగతులు ప్లాన్ చేయలేదు"],
  classesHeld: ["{done} of {total} classes held", "{total} తరగతులలో {done} జరిగాయి"],
  breadcrumbMyLearning: ["My Learning", "నా అభ్యాసం"],
  moduleTopicsDone: ["{done} of {total} done", "{total} లో {done} పూర్తి"],
  required: ["Required", "తప్పనిసరి"],
  optional: ["Optional", "ఐచ్ఛికం"],
  topicClasses: ["Classes", "తరగతులు"],
  topicRecording: ["Recording", "రికార్డింగ్"],
  topicMaterials: ["Class materials", "తరగతి సామగ్రి"],
  topicWork: ["Assignments and tests", "అసైన్‌మెంట్‌లు, పరీక్షలు"],
  topicNoClass: [
    "No class covers this topic yet. Classes appear here once your branch schedules them.",
    "ఈ అంశాన్ని ఏ తరగతీ కవర్ చేయడం లేదు. మీ బ్రాంచ్ షెడ్యూల్ చేయగానే తరగతులు ఇక్కడ కనిపిస్తాయి.",
  ],
  topicNoRecording: [
    "No recording yet. It appears here after the class, once it is released.",
    "ఇంకా రికార్డింగ్ లేదు. తరగతి తర్వాత విడుదలైనప్పుడు ఇక్కడ కనిపిస్తుంది.",
  ],
  topicNoMaterials: ["No files for this topic yet.", "ఈ అంశానికి ఇంకా ఫైళ్ళు లేవు."],
  topicNoWork: ["No assignment or test for this topic.", "ఈ అంశానికి అసైన్‌మెంట్ లేదా పరీక్ష లేదు."],
  topicHowDone: ["How a topic gets done", "ఒక అంశం ఎలా పూర్తవుతుంది"],
  topicHowDoneText: [
    "A topic is done when you attended its class, or watched its recording, and handed in the required assignments and tests for it.",
    "మీరు ఆ అంశం తరగతికి హాజరైతే లేదా దాని రికార్డింగ్ చూస్తే, మరియు దానికి అవసరమైన అసైన్‌మెంట్‌లు, పరీక్షలు సమర్పిస్తే ఆ అంశం పూర్తయినట్లు.",
  ],
  topicDoneNote: ["Done. You attended or watched, and handed in what was required.", "పూర్తయింది. మీరు హాజరయ్యారు లేదా చూశారు, అవసరమైనవి సమర్పించారు."],
  topicWorkNote: [
    "You have taken the class. Hand in the required work to finish this topic.",
    "మీరు తరగతికి హాజరయ్యారు. ఈ అంశాన్ని పూర్తి చేయడానికి అవసరమైన పనిని సమర్పించండి.",
  ],
  topicStartNote: ["Attend the class or watch the recording to start this topic.", "ఈ అంశాన్ని మొదలుపెట్టడానికి తరగతికి హాజరవండి లేదా రికార్డింగ్ చూడండి."],
  nextTopic: ["Next topic", "తదుపరి అంశం"],
  lastTopic: ["This is the last topic.", "ఇది చివరి అంశం."],
  notMarkedYet: ["Attendance not marked yet", "హాజరు ఇంకా నమోదు కాలేదు"],
  statusFor: ["Status", "స్థితి"],
  slot_title: ["Preferred slot", "ఇష్టమైన స్లాట్"],
  slot_none_course: ["You have no course to ask about yet.", "మీకు ఇంకా అడగడానికి కోర్సు లేదు."],
  slot_none_open: ["You have no open slot request for this course.", "ఈ కోర్సుకు మీకు తెరిచి ఉన్న స్లాట్ అభ్యర్థన లేదు."],
  slot_no_batches: [
    "No open batch is listed for your course at your branch right now. You can still say which days and times suit you.",
    "ప్రస్తుతం మీ బ్రాంచ్‌లో మీ కోర్సుకు తెరిచి ఉన్న బ్యాచ్ లేదు. అయినా మీకు ఏ రోజులు, సమయాలు అనుకూలమో చెప్పవచ్చు.",
  ],
  slot_course_label: ["Course for the slot request", "స్లాట్ అభ్యర్థన కోసం కోర్సు"],
  slot_note: [
    "A request does not reserve a seat. A seat comes only from an allocation to a batch, which your Branch Manager makes after checking the batch has room.",
    "అభ్యర్థన సీటును రిజర్వ్ చేయదు. బ్యాచ్‌లో స్థలం ఉందో లేదో చూసి మీ బ్రాంచ్ మేనేజర్ కేటాయిస్తేనే సీటు వస్తుంది.",
  ],
  slot_request_button: ["Request a preferred slot", "ఇష్టమైన స్లాట్ కోసం అభ్యర్థించండి"],
  slot_request_help: [
    "Choose a batch, or say which days and times suit you. A request does not reserve a seat.",
    "ఒక బ్యాచ్‌ను ఎంచుకోండి, లేదా మీకు ఏ రోజులు, సమయాలు అనుకూలమో చెప్పండి. అభ్యర్థన సీటును రిజర్వ్ చేయదు.",
  ],
  slot_batch_field: ["A batch you would like", "మీరు కోరుకునే బ్యాచ్"],
  slot_no_batch: ["No particular batch", "ప్రత్యేక బ్యాచ్ లేదు"],
  slot_days: ["Days that suit you", "మీకు అనుకూలమైన రోజులు"],
  slot_start: ["Earliest start (IST)", "ముందుగా మొదలు (IST)"],
  slot_end: ["Latest finish (IST)", "చివరగా ముగింపు (IST)"],
  slot_mode: ["How you would attend", "మీరు ఎలా హాజరవుతారు"],
  slot_any: ["Any", "ఏదైనా"],
  slot_anything: ["Anything we should know", "మేము తెలుసుకోవలసినది ఏదైనా"],
  slot_send: ["Send request", "అభ్యర్థన పంపండి"],
  slot_sent: ["Request sent. It does not reserve a seat.", "అభ్యర్థన పంపబడింది. ఇది సీటును రిజర్వ్ చేయదు."],
  slot_withdraw: ["Withdraw request", "అభ్యర్థనను ఉపసంహరించండి"],
  slot_withdrawn: ["Request withdrawn", "అభ్యర్థన ఉపసంహరించబడింది"],
  slot_your_request: ["Your request", "మీ అభ్యర్థన"],
  slot_your_note: ["Your note: {note}", "మీ గమనిక: {note}"],
  slot_from_team: ["From your branch: {note}", "మీ బ్రాంచ్ నుండి: {note}"],
  slot_requested_on: ["Requested {when}.", "{when} న అభ్యర్థించారు."],
  enrol_note_provisioning: [
    "Your course content opens once the qualifying payment is verified.",
    "అర్హత చెల్లింపు ధృవీకరించబడిన తర్వాత మీ కోర్సు కంటెంట్ తెరుచుకుంటుంది.",
  ],
  enrol_note_allocation: [
    "Your course is confirmed. Your branch will give you a batch before your first class.",
    "మీ కోర్సు నిర్ధారించబడింది. మొదటి తరగతికి ముందు మీ బ్రాంచ్ మీకు బ్యాచ్ ఇస్తుంది.",
  ],
  enrol_note_allocated: [
    "You have a batch. Your joining date is set when you attend your first regular class.",
    "మీకు బ్యాచ్ ఉంది. మీ మొదటి సాధారణ తరగతికి హాజరైనప్పుడు మీ చేరిన తేదీ నిర్ణయమవుతుంది.",
  ],
  enrol_note_paused: [
    "This course is paused. Ask your Branch Manager to resume it.",
    "ఈ కోర్సు నిలిపివేయబడింది. దీన్ని మళ్ళీ మొదలుపెట్టమని మీ బ్రాంచ్ మేనేజర్‌ను అడగండి.",
  ],
  enrol_note_completed: ["You have completed this course.", "మీరు ఈ కోర్సును పూర్తి చేశారు."],
  enrol_note_withdrawn: ["This enrolment has ended.", "ఈ నమోదు ముగిసింది."],
  kind_combo: ["Combo programme", "కాంబో ప్రోగ్రామ్"],
  kind_standalone: ["Single course", "ఒకే కోర్సు"],
  kind_separate: ["Bought separately", "విడిగా కొన్నది"],
  kind_complimentary: ["Included free", "ఉచితంగా చేర్చబడింది"],
  // statuses (lib/status.ts `tkey`)
  st_enrol_provisioning: ["Access being set up", "యాక్సెస్ సిద్ధమవుతోంది"],
  st_enrol_allocation: ["Waiting for a batch", "బ్యాచ్ కోసం వేచి ఉన్నారు"],
  st_enrol_allocated: ["Batch allocated", "బ్యాచ్ కేటాయించబడింది"],
  st_enrol_active: ["In progress", "కొనసాగుతోంది"],
  st_enrol_paused: ["Paused", "నిలిపివేయబడింది"],
  st_enrol_completed: ["Completed", "పూర్తయింది"],
  st_enrol_withdrawn: ["Withdrawn", "ఉపసంహరించబడింది"],
  st_topic_done: ["Done", "పూర్తయింది"],
  st_topic_work: ["Work to hand in", "సమర్పించాల్సిన పని ఉంది"],
  st_topic_not_started: ["Not started", "మొదలు కాలేదు"],
  st_session_planned: ["Planned", "ప్రణాళికలో ఉంది"],
  st_session_confirmed: ["Confirmed", "నిర్ధారించబడింది"],
  st_session_scheduled: ["Scheduled", "షెడ్యూల్ చేయబడింది"],
  st_session_not_scheduled: ["Not scheduled", "షెడ్యూల్ కాలేదు"],
  st_session_in_delivery: ["Being taught", "బోధన జరుగుతోంది"],
  st_session_live: ["Live", "ఇప్పుడు జరుగుతోంది"],
  st_session_held: ["Held", "జరిగింది"],
  st_session_partly: ["Partly held", "పాక్షికంగా జరిగింది"],
  st_session_not_held: ["Not held", "జరగలేదు"],
  st_session_cancelled: ["Cancelled", "రద్దు చేయబడింది"],
  st_session_moved: ["Moved", "మార్చబడింది"],
  st_work_upcoming: ["Upcoming", "రాబోయేది"],
  st_work_due: ["Due soon", "త్వరలో గడువు"],
  st_work_overdue: ["Overdue", "గడువు దాటింది"],
  st_work_submitted: ["Submitted", "సమర్పించబడింది"],
  st_work_reviewing: ["Being reviewed", "సమీక్షలో ఉంది"],
  st_work_reviewed: ["Reviewed", "సమీక్షించబడింది"],
  st_work_resubmit: ["Resubmit", "మళ్ళీ సమర్పించండి"],
  st_att_present: ["Present", "హాజరు"],
  st_att_absent: ["Absent", "గైర్హాజరు"],
  st_att_late: ["Late", "ఆలస్యం"],
  st_att_excused: ["Excused", "మినహాయింపు"],
  st_rec_processing: ["Being prepared", "సిద్ధమవుతోంది"],
  st_rec_available: ["Available", "అందుబాటులో ఉంది"],
  st_rec_partial: ["Partly available", "పాక్షికంగా అందుబాటులో ఉంది"],
  st_rec_held: ["On hold", "నిలిపివేయబడింది"],
  st_rec_unavailable: ["Not available", "అందుబాటులో లేదు"],
  st_rec_expired: ["Access ended", "యాక్సెస్ ముగిసింది"],
  st_test_open: ["Open", "తెరిచి ఉంది"],
  st_test_closed: ["Closed", "ముగిసింది"],
  st_test_scheduled: ["Scheduled", "షెడ్యూల్ చేయబడింది"],
} as const satisfies Record<string, readonly [string, string]>;

export type TranslationKey = keyof typeof DICTIONARY;

const KEY_PREFIX = "nipuna-lms-lang";
const listeners = new Set<() => void>();
/** Choices made this session; used when localStorage is unavailable. */
const memory = new Map<string, Language>();

const storageKey = (userId: number | null) => (userId ? `${KEY_PREFIX}:${userId}` : KEY_PREFIX);

function readStored(userId: number | null): Language | null {
  const chosen = memory.get(storageKey(userId));
  if (chosen) return chosen;
  try {
    const value = window.localStorage.getItem(storageKey(userId));
    return value === "en" || value === "te" ? value : null;
  } catch {
    return null;
  }
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => void listeners.delete(listener);
}

/** Current language and its setter. Signed-in users keep their own choice; the sign-in screen has a shared one. */
export function useLanguage() {
  const { profile } = useAuth();
  const userId = profile?.user.user_id ?? null;
  const fallback = profile?.student?.preferred_language ?? "en";
  const stored = useSyncExternalStore(subscribe, () => readStored(userId));
  const setLang = useCallback(
    (next: Language) => {
      memory.set(storageKey(userId), next);
      try {
        window.localStorage.setItem(storageKey(userId), next);
      } catch {
        /* storage unavailable: the choice lasts until reload */
      }
      listeners.forEach((l) => l());
    },
    [userId],
  );
  return { lang: stored ?? fallback, setLang };
}

/** `const t = useT(); t("home")`. A `{name}` in the text is filled from `values`: `t("welcomeName", { name })`. */
export function useT() {
  const { lang } = useLanguage();
  return useCallback(
    (key: TranslationKey, values?: Record<string, string | number>) => {
      const text: string = DICTIONARY[key][lang === "en" ? 0 : 1];
      return values ? text.replace(/\{(\w+)\}/g, (whole, name: string) => String(values[name] ?? whole)) : text;
    },
    [lang],
  );
}

/** `const pick = useLocalised(); pick(topic.title, topic.title_te)`: the Telugu text when the reader chose Telugu and there is one. */
export function useLocalised() {
  const { lang } = useLanguage();
  return useCallback((english: string, telugu?: string | null) => (lang === "te" && telugu ? telugu : english), [lang]);
}

/** Keeps <html lang> in step with the chosen language while a translated screen is showing (Telugu switches the font). */
export function useDocumentLanguage(translated: boolean) {
  const { lang } = useLanguage();
  useEffect(() => {
    document.documentElement.lang = translated ? lang : "en";
  }, [lang, translated]);
}
