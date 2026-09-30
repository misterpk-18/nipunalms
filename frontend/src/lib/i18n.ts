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
  forgotHelp: [
    "Ask your branch Academic Coordinator to reissue an activation link.",
    "కొత్త యాక్టివేషన్ లింక్ కోసం మీ బ్రాంచ్ అకడమిక్ కోఆర్డినేటర్‌ను అడగండి.",
  ],
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

/** `const t = useT(); t("home")`. */
export function useT() {
  const { lang } = useLanguage();
  return useCallback((key: TranslationKey) => DICTIONARY[key][lang === "en" ? 0 : 1], [lang]);
}

/** Keeps <html lang> in step with the chosen language while a translated screen is showing (Telugu switches the font). */
export function useDocumentLanguage(translated: boolean) {
  const { lang } = useLanguage();
  useEffect(() => {
    document.documentElement.lang = translated ? lang : "en";
  }, [lang, translated]);
}
