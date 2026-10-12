import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { Button, Checkbox, Dialog } from "@/components/ui";
import { useMe, useUpdateMe } from "@/features/auth/api";
import type { Language } from "@/lib/types";

import { CHANGELOG, LATEST, unseen, type ChangelogEntry } from "./changelog";

export type OnboardingView = "welcome" | "news" | null;

const STEPS = ["trees", "explore", "builder", "archive", "discover", "share"] as const;
// Shown at most once per browser session (the guide comes back at the next sign-in).
const SESSION_KEY = "korinnia.onboarding.shown";

function shownThisSession(userId: string): boolean {
  try {
    return sessionStorage.getItem(SESSION_KEY) === userId;
  } catch {
    return false;
  }
}

function markShown(userId: string) {
  try {
    sessionStorage.setItem(SESSION_KEY, userId);
  } catch {
    // Private mode without storage: the guide may simply show again.
  }
}

/**
 * Pops up the welcome guide (until the user ticks "don't show again") or, for those who
 * know the app, what is new since their last visit. `view` / `onView` also let the footer
 * open either one on request.
 */
export function Onboarding({
  view,
  onView,
}: {
  view: OnboardingView;
  onView: (view: OnboardingView) => void;
}) {
  const me = useMe();
  const user = me.data;
  useEffect(() => {
    if (!user || view || shownThisSession(user.id)) return;
    if (!user.welcome_dismissed) onView("welcome");
    else if (user.show_changelog && unseen(user.changelog_seen).length) onView("news");
    markShown(user.id);
  }, [user, view, onView]);

  if (!user) return null;
  if (view === "welcome")
    return <WelcomeDialog dismissed={user.welcome_dismissed} onClose={() => onView(null)} />;
  if (view === "news")
    return (
      <NewsDialog
        entries={
          user.changelog_seen && unseen(user.changelog_seen).length
            ? unseen(user.changelog_seen)
            : CHANGELOG
        }
        showAtSignIn={user.show_changelog}
        onClose={() => onView(null)}
      />
    );
  return null;
}

function WelcomeDialog({ dismissed, onClose }: { dismissed: boolean; onClose: () => void }) {
  const { t } = useTranslation();
  const update = useUpdateMe();
  const [never, setNever] = useState(dismissed);
  const close = () => {
    // Whoever has read the guide has also had all the news.
    update.mutate({ welcome_dismissed: never, changelog_seen: LATEST });
    onClose();
  };
  return (
    <Dialog open title={t("welcome.title")} onClose={close}>
      <div className="space-y-4 text-sm">
        <p>{t("welcome.intro")}</p>
        <ol className="space-y-3">
          {STEPS.map((step, i) => (
            <li key={step} className="flex gap-3">
              <span className="bg-leaf-700 text-on-leaf flex size-6 shrink-0 items-center justify-center rounded-full text-xs font-semibold">
                {i + 1}
              </span>
              <span>
                <span className="font-semibold">{t(`welcome.steps.${step}.title`)}</span>{" "}
                <span className="text-bark-700">{t(`welcome.steps.${step}.text`)}</span>
              </span>
            </li>
          ))}
        </ol>
        <p>
          <Link to="/help" onClick={close} className="text-leaf-700 underline">
            {t("welcome.fullGuide")}
          </Link>
        </p>
        <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
          <Checkbox
            label={t("welcome.dontShow")}
            checked={never}
            onChange={(e) => setNever(e.target.checked)}
          />
          <Button onClick={close}>{t("welcome.start")}</Button>
        </div>
      </div>
    </Dialog>
  );
}

function NewsDialog({
  entries,
  showAtSignIn,
  onClose,
}: {
  entries: ChangelogEntry[];
  showAtSignIn: boolean;
  onClose: () => void;
}) {
  const { t, i18n } = useTranslation();
  const update = useUpdateMe();
  const [quiet, setQuiet] = useState(!showAtSignIn);
  const lang = (i18n.resolvedLanguage ?? "en") as Language;
  const close = () => {
    update.mutate({ changelog_seen: LATEST, show_changelog: !quiet });
    onClose();
  };
  const date = (id: string) =>
    new Intl.DateTimeFormat(i18n.language, { dateStyle: "long" }).format(
      new Date(`${id.slice(0, 10)}T12:00:00`), // "2026-10-11.2" → its day
    );
  return (
    <Dialog open title={t("news.title")} onClose={close}>
      <div className="space-y-4 text-sm">
        <div className="max-h-[60vh] space-y-4 overflow-y-auto pr-1">
          {entries.map((entry) => (
            <section key={entry.id}>
              <h3 className="text-bark-700 mb-1 text-xs font-semibold tracking-wide uppercase">
                {date(entry.id)}
              </h3>
              <ul className="list-disc space-y-1 pl-5">
                {(entry.items[lang] ?? entry.items.en).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </section>
          ))}
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Checkbox
            label={t("news.dontShow")}
            checked={quiet}
            onChange={(e) => setQuiet(e.target.checked)}
          />
          <Button onClick={close}>{t("news.ok")}</Button>
        </div>
      </div>
    </Dialog>
  );
}
