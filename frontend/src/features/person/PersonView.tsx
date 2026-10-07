import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { Markdown } from "@/components/Markdown";
import { Badge, Button } from "@/components/ui";
import { CitationList } from "@/features/collab/CitationList";
import { CommentsThread } from "@/features/collab/CommentsThread";
import { QuestionsList } from "@/features/collab/QuestionsList";
import { SuggestEditDialog } from "@/features/collab/SuggestEditDialog";
import { formatPartialDate, lifeYears } from "@/lib/dates";
import type { LifeEvent, PersonDetail, PersonSummary, PlaceSummary } from "@/lib/genealogy";
import { atLeast, type Role } from "@/lib/types";

import { MediaSections } from "@/features/media/MediaSections";

import { Avatar } from "./Avatar";

export type PersonLink = (personId: string) => string;

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-2">
      <h3 className="text-bark-700 text-xs font-semibold tracking-wide uppercase">{title}</h3>
      {children}
    </section>
  );
}

function PlaceText({ place }: { place: PlaceSummary | null }) {
  if (!place) return null;
  const extra = [place.region, place.country].filter(Boolean).join(", ");
  return (
    <span>
      {place.name}
      {extra && <span className="text-bark-700"> ({extra})</span>}
    </span>
  );
}

function osmLink(lat: string, lon: string): string {
  return `https://www.openstreetmap.org/?mlat=${lat}&mlon=${lon}#map=17/${lat}/${lon}`;
}

function RelativeLink({
  person,
  to,
  note,
}: {
  person: PersonSummary;
  to: PersonLink;
  note?: string;
}) {
  return (
    <li>
      <Link to={to(person.id)} className="text-leaf-700 hover:underline">
        {person.display_name}
      </Link>
      <span className="text-bark-700 text-sm">
        {" "}
        {lifeYears(person.birth, person.death, person.is_living)}
        {note && ` · ${note}`}
      </span>
    </li>
  );
}

export function PersonView({
  person,
  personLink,
  showWarnings = false,
  treeId,
  role,
}: {
  person: PersonDetail;
  personLink: PersonLink;
  showWarnings?: boolean;
  /** With tree + role: research questions, comments and suggestions are interactive. */
  treeId?: string;
  role?: Role;
}) {
  const { t, i18n } = useTranslation();
  const [suggesting, setSuggesting] = useState(false);
  const canContribute = role ? atLeast(role, "contributor") : false;
  const fmt = (d: Parameters<typeof formatPartialDate>[0]) =>
    formatPartialDate(d, t, i18n.language);
  const burial = person.events.find((e) => e.type === "burial");
  const timeline = person.events;
  const facts: [string, ReactNode][] = [];
  if (person.birth) {
    facts.push([
      t("person.born"),
      <>
        {fmt(person.birth.date)} {person.birth.place && <PlaceText place={person.birth.place} />}
      </>,
    ]);
  }
  if (person.death) {
    facts.push([
      t("person.died"),
      <>
        {fmt(person.death.date)} {person.death.place && <PlaceText place={person.death.place} />}
      </>,
    ]);
  }
  if (burial) {
    facts.push([
      t("person.buried"),
      <>
        {[fmt(burial.date), burial.cemetery_name, burial.burial_plot].filter(Boolean).join(", ")}{" "}
        {burial.place && <PlaceText place={burial.place} />}
        {burial.latitude && burial.longitude && (
          <>
            {" · "}
            <a
              className="text-leaf-700 underline"
              href={osmLink(burial.latitude, burial.longitude)}
              target="_blank"
              rel="noopener noreferrer"
            >
              {t("person.onMap")}
            </a>
          </>
        )}
      </>,
    ]);
  }
  for (const key of ["occupation", "education", "religion", "nationality"] as const) {
    const value = person[key];
    if (value) facts.push([t(`person.${key}`), value]);
  }

  return (
    <article className="space-y-6">
      <header className="flex items-start gap-4">
        <Avatar
          name={person.display_name}
          gender={person.gender}
          url={person.avatar_url}
          size="lg"
        />
        <div className="min-w-0 space-y-1">
          <h2 className="font-serif text-2xl leading-tight font-semibold">{person.display_name}</h2>
          <p className="text-bark-700">
            {lifeYears(person.birth?.date ?? null, person.death?.date ?? null, person.is_living)}
          </p>
          {person.short_summary && <p className="text-sm">{person.short_summary}</p>}
          <div className="flex flex-wrap items-center gap-1">
            {person.is_living && <Badge tone="green">{t("person.living")}</Badge>}
            <Badge>
              {t("person.researchStatus")}: {t(`research.${person.research_status}`)}
            </Badge>
            {treeId && (
              <span className="ml-1 flex flex-wrap gap-3 text-sm print:hidden">
                <Link
                  to={`/trees/${treeId}/relationship?a=${person.id}`}
                  className="text-leaf-700 hover:underline"
                >
                  {t("insights.kinship.howRelated")}
                </Link>
                <Link
                  to={`/trees/${treeId}/map?person=${person.id}`}
                  className="text-leaf-700 hover:underline"
                >
                  {t("insights.map.onMap")}
                </Link>
                <Link
                  to={`/trees/${treeId}/timeline?person=${person.id}`}
                  className="text-leaf-700 hover:underline"
                >
                  {t("insights.nav.timeline")}
                </Link>
              </span>
            )}
            {treeId && role === "contributor" && (
              <Button
                variant="secondary"
                className="ml-1 print:hidden"
                onClick={() => setSuggesting(true)}
              >
                {t("collab.suggest.button")}
              </Button>
            )}
          </div>
        </div>
      </header>

      {facts.length > 0 && (
        <Section title={t("person.facts")}>
          <dl className="grid grid-cols-[minmax(6rem,auto)_1fr] gap-x-4 gap-y-1 text-sm">
            {facts.map(([label, value]) => (
              <div key={label} className="contents">
                <dt className="text-bark-700">{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        </Section>
      )}

      {person.names.length > 1 && (
        <Section title={t("person.names")}>
          <ul className="space-y-1 text-sm">
            {person.names.map((n) => (
              <li key={n.id}>
                <span className={n.is_primary ? "font-medium" : ""}>{n.display}</span>
                <span className="text-bark-700">
                  {" "}
                  · {t(`nameTypes.${n.type}`)} · {t(`scripts.${n.script}`)}
                </span>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {person.biography && (
        <Section title={t("person.biography")}>
          <Markdown>{person.biography}</Markdown>
        </Section>
      )}

      <MediaSections
        media={person.media}
        personLink={personLink}
        Section={Section}
        comments={treeId && role ? { treeId, role } : undefined}
      />

      <Section title={t("person.timeline")}>
        {timeline.length === 0 ? (
          <p className="text-bark-700 text-sm">{t("person.noEvents")}</p>
        ) : (
          <ol className="border-bark-100 relative space-y-3 border-l-2 pl-4">
            {timeline.map((ev) => (
              <TimelineItem key={ev.id} event={ev} personId={person.id} personLink={personLink} />
            ))}
          </ol>
        )}
      </Section>

      <Section title={t("person.relatives")}>
        <div className="grid gap-4 sm:grid-cols-2">
          {person.parents.length > 0 && (
            <div>
              <h4 className="text-sm font-medium">{t("person.parents")}</h4>
              <ul className="text-sm">
                {person.parents.map((r) => (
                  <RelativeLink
                    key={r.relationship_id}
                    person={r.person}
                    to={personLink}
                    note={t(`relTypes.${r.type}`) || undefined}
                  />
                ))}
              </ul>
            </div>
          )}
          {person.partners.length > 0 && (
            <div>
              <h4 className="text-sm font-medium">{t("person.partners")}</h4>
              <ul className="text-sm">
                {person.partners.map((p) => (
                  <RelativeLink
                    key={p.partnership_id}
                    person={p.person}
                    to={personLink}
                    note={[
                      t(`partnershipTypes.${p.type}`),
                      p.start_date && t("person.since", { date: fmt(p.start_date) }),
                      p.end_reason && t(`endReasons.${p.end_reason}`),
                    ]
                      .filter(Boolean)
                      .join(", ")}
                  />
                ))}
              </ul>
            </div>
          )}
          {person.children.length > 0 && (
            <div>
              <h4 className="text-sm font-medium">{t("person.children")}</h4>
              <ul className="text-sm">
                {person.children.map((r) => (
                  <RelativeLink
                    key={r.relationship_id}
                    person={r.person}
                    to={personLink}
                    note={t(`relTypes.${r.type}`) || undefined}
                  />
                ))}
              </ul>
            </div>
          )}
          {person.siblings.length > 0 && (
            <div>
              <h4 className="text-sm font-medium">{t("person.siblings")}</h4>
              <ul className="text-sm">
                {person.siblings.map((s) => (
                  <RelativeLink
                    key={s.person.id}
                    person={s.person}
                    to={personLink}
                    note={s.half ? t("person.halfSibling") : undefined}
                  />
                ))}
              </ul>
            </div>
          )}
        </div>
      </Section>

      {person.notes_for_descendants && (
        <Section title={t("person.notesForDescendants")}>
          <div className="rounded-md border border-amber-200 bg-amber-50 p-3">
            <Markdown>{person.notes_for_descendants}</Markdown>
          </div>
        </Section>
      )}

      {person.citations.length > 0 && (
        <Section title={t("collab.sources")}>
          <CitationList citations={person.citations} />
        </Section>
      )}

      {person.stories.length > 0 && treeId && (
        <Section title={t("collab.stories")}>
          <ul className="space-y-2 text-sm">
            {person.stories.map((s) => (
              <li key={s.id}>
                <Link
                  to={`/trees/${treeId}/stories/${s.id}`}
                  className="text-leaf-700 font-medium hover:underline"
                >
                  {s.title}
                </Link>
                {s.status !== "published" && (
                  <Badge tone="amber">{t(`collab.storyStatus.${s.status}`)}</Badge>
                )}
                <p className="text-bark-700">{s.excerpt}</p>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {treeId && (person.open_questions.length > 0 || canContribute) && (
        <Section title={t("collab.questions.title")}>
          <QuestionsList
            treeId={treeId}
            personId={person.id}
            questions={person.open_questions}
            canWrite={canContribute}
          />
        </Section>
      )}

      {showWarnings && person.warnings.length > 0 && (
        <Section title={t("person.dataNotes")}>
          <ul className="list-disc space-y-1 pl-5 text-sm text-amber-800">
            {person.warnings.map((w, i) => (
              <li key={`${w.code}-${i}`}>
                {t(`warnings.${w.code}`, { ...w.params, defaultValue: w.code })}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {treeId && role && (
        <Section title={t("collab.comments.title")}>
          <CommentsThread
            treeId={treeId}
            entityType="person"
            entityId={person.id}
            canWrite={canContribute}
            canModerate={atLeast(role, "editor")}
          />
        </Section>
      )}
      {suggesting && treeId && (
        <SuggestEditDialog treeId={treeId} person={person} onClose={() => setSuggesting(false)} />
      )}
    </article>
  );
}

function TimelineItem({
  event,
  personId,
  personLink,
}: {
  event: LifeEvent;
  personId: string;
  personLink: PersonLink;
}) {
  const { t, i18n } = useTranslation();
  const others = event.participants.filter((p) => p.person_id !== personId);
  return (
    <li className="relative">
      <span
        className="bg-leaf-600 absolute top-1.5 -left-[1.4rem] size-2.5 rounded-full"
        aria-hidden
      />
      <div className="text-bark-700 text-sm">{formatPartialDate(event.date, t, i18n.language)}</div>
      <div className="font-medium">
        {t(`eventTypes.${event.type}`, { defaultValue: event.type })}
        {event.title && `: ${event.title}`}
      </div>
      {event.place && (
        <div className="text-sm">
          <PlaceText place={event.place} />
        </div>
      )}
      {others.length > 0 && (
        <div className="text-sm">
          {others.map((p, i) => (
            <span key={p.person_id}>
              {i > 0 && ", "}
              <Link to={personLink(p.person_id)} className="text-leaf-700 hover:underline">
                {p.display_name}
              </Link>
            </span>
          ))}
        </div>
      )}
      {event.description && <Markdown className="text-sm">{event.description}</Markdown>}
    </li>
  );
}
