import { useState } from "react";
import { useTranslation } from "react-i18next";

import {
  Alert,
  Button,
  CopyField,
  Dialog,
  ErrorAlert,
  Field,
  Select,
  Spinner,
} from "@/components/ui";
import { SUPPORTED_LANGUAGES } from "@/i18n";
import { useFormatDate } from "@/lib/hooks";
import type { Language } from "@/lib/types";

import {
  useCalendarFeed,
  useCreateCalendarFeed,
  useRevokeCalendarFeed,
  useUpdateCalendarFeed,
  type CreatedCalendarFeed,
} from "./api";

/** "Subscribe in your calendar": a private iCalendar feed of the tree's birthdays, memorial
 * days and wedding anniversaries (D115). The URL is shown once, when it is created. */
export function CalendarFeedDialog({ treeId, onClose }: { treeId: string; onClose: () => void }) {
  const { t, i18n } = useTranslation();
  const formatDate = useFormatDate();
  const feed = useCalendarFeed(treeId);
  const create = useCreateCalendarFeed(treeId);
  const update = useUpdateCalendarFeed(treeId);
  const revoke = useRevokeCalendarFeed(treeId);
  const [created, setCreated] = useState<CreatedCalendarFeed | null>(null);
  const [language, setLanguage] = useState<Language>(
    (i18n.resolvedLanguage as Language | undefined) ?? "uk",
  );

  const make = (lang: Language) => create.mutate(lang, { onSuccess: (r) => setCreated(r) });

  const languagePicker = (value: Language, onChange: (lang: Language) => void) => (
    <Field label={t("calendarFeed.language")}>
      {(id) => (
        <Select
          id={id}
          className="w-auto"
          value={value}
          onChange={(e) => onChange(e.target.value as Language)}
        >
          {SUPPORTED_LANGUAGES.map((lang) => (
            <option key={lang.code} value={lang.code}>
              {lang.label}
            </option>
          ))}
        </Select>
      )}
    </Field>
  );

  return (
    <Dialog open onClose={onClose} title={t("calendarFeed.title")}>
      <div className="space-y-4 text-sm">
        <p className="text-bark-700">{t("calendarFeed.hint")}</p>
        <ErrorAlert error={feed.error ?? create.error ?? update.error ?? revoke.error} />
        {feed.isPending && <Spinner />}

        {created && (
          <div className="space-y-3" data-testid="calendar-feed-created">
            <Alert kind="success">{t("calendarFeed.created")}</Alert>
            <CopyField value={created.url} />
            <a
              href={created.webcal_url}
              className="text-leaf-700 inline-block font-medium underline"
            >
              {t("calendarFeed.openInApp")}
            </a>
            <ul className="text-bark-700 list-disc space-y-1 pl-5 text-xs">
              <li>{t("calendarFeed.howTo.google")}</li>
              <li>{t("calendarFeed.howTo.apple")}</li>
              <li>{t("calendarFeed.howTo.outlook")}</li>
            </ul>
          </div>
        )}

        {feed.data && (
          <section className="border-bark-100 space-y-3 border-t pt-3">
            <p data-testid="calendar-feed-status">
              {t("calendarFeed.since", { date: formatDate(feed.data.created_at, false) })}{" "}
              {feed.data.last_used_at
                ? t("calendarFeed.lastUsed", { date: formatDate(feed.data.last_used_at) })
                : t("calendarFeed.notUsedYet")}
            </p>
            {languagePicker(feed.data.language, (lang) => update.mutate(lang))}
            <div className="flex flex-wrap gap-2">
              {!created && (
                <Button
                  variant="secondary"
                  busy={create.isPending}
                  onClick={() => {
                    if (window.confirm(t("calendarFeed.confirmRenew"))) make(feed.data!.language);
                  }}
                >
                  {t("calendarFeed.renew")}
                </Button>
              )}
              <Button
                variant="danger"
                busy={revoke.isPending}
                onClick={() => {
                  if (!window.confirm(t("calendarFeed.confirmRevoke"))) return;
                  revoke.mutate(undefined, { onSuccess: () => setCreated(null) });
                }}
              >
                {t("calendarFeed.revoke")}
              </Button>
            </div>
          </section>
        )}

        {feed.data === null && (
          <div className="space-y-3">
            {languagePicker(language, setLanguage)}
            <Button busy={create.isPending} onClick={() => make(language)}>
              {t("calendarFeed.create")}
            </Button>
          </div>
        )}

        <div className="flex justify-end">
          <Button variant="secondary" onClick={onClose}>
            {t("common.close")}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
