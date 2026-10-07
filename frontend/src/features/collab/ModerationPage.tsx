import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router";

import { Button, Card, ErrorAlert, PageHeader, Spinner, TextArea } from "@/components/ui";
import { useFormatDate } from "@/lib/hooks";
import type { Suggestion } from "@/lib/genealogy";

import { useReviewSuggestion, useStories, useSuggestions } from "./api";

function show(v: unknown): string {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "string") return v;
  return JSON.stringify(v, null, 1);
}

/** Editors review contributors' suggestions and stories. */
export function ModerationPage() {
  const { t } = useTranslation();
  const { treeId = "" } = useParams();
  const suggestions = useSuggestions(treeId, "pending");
  const stories = useStories(treeId, { status: "pending_review" });
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <Link to={`/trees/${treeId}`} className="text-leaf-700 text-sm underline">
        ← {t("person.backToTree")}
      </Link>
      <PageHeader title={t("collab.moderation.title")} />
      <section className="space-y-3">
        <h2 className="font-semibold">{t("collab.moderation.suggestions")}</h2>
        {suggestions.isPending && <Spinner />}
        <ErrorAlert error={suggestions.error} />
        {suggestions.data?.length === 0 && (
          <p className="text-bark-700 text-sm">{t("collab.moderation.noneSuggestions")}</p>
        )}
        {suggestions.data?.map((s) => (
          <SuggestionCard key={s.id} treeId={treeId} suggestion={s} />
        ))}
      </section>
      <section className="space-y-3">
        <h2 className="font-semibold">{t("collab.moderation.stories")}</h2>
        {stories.data?.items.length === 0 && (
          <p className="text-bark-700 text-sm">{t("collab.moderation.noneStories")}</p>
        )}
        <ul className="space-y-2">
          {stories.data?.items.map((s) => (
            <li key={s.id}>
              <Card>
                <Link
                  to={`/trees/${treeId}/stories/${s.id}`}
                  className="text-leaf-700 font-medium hover:underline"
                >
                  {s.title}
                </Link>
                <div className="text-bark-700 text-xs">{s.author?.display_name}</div>
                <p className="text-bark-700 text-sm">{s.excerpt}</p>
              </Card>
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

function SuggestionCard({ treeId, suggestion: s }: { treeId: string; suggestion: Suggestion }) {
  const { t } = useTranslation();
  const formatDate = useFormatDate();
  const review = useReviewSuggestion(treeId);
  const [comment, setComment] = useState("");
  const link = s.entity_type === "person" ? `/trees/${treeId}/people/${s.entity_id}` : null;
  return (
    <Card className="space-y-3">
      <div className="text-sm">
        {link ? (
          <Link to={link} className="text-leaf-700 font-medium underline">
            {s.entity_label}
          </Link>
        ) : (
          <span className="font-medium">
            {t(`eventTypes.${s.entity_label}`, { defaultValue: s.entity_label })}
          </span>
        )}
        <span className="text-bark-700">
          {" "}
          · {s.author?.display_name} · {formatDate(s.created_at)}
        </span>
      </div>
      {s.comment && <p className="text-sm italic">“{s.comment}”</p>}
      <table className="w-full table-fixed text-left text-sm">
        <thead className="text-bark-700 text-xs">
          <tr>
            <th className="w-1/5 py-1">{t("collab.moderation.field")}</th>
            <th className="py-1">{t("audit.before")}</th>
            <th className="py-1">{t("audit.after")}</th>
          </tr>
        </thead>
        <tbody className="divide-bark-100 divide-y align-top">
          {Object.keys(s.patch).map((f) => (
            <tr key={f}>
              <td className="py-1 pr-2">{t(`collab.fields.${f}`, { defaultValue: f })}</td>
              <td className="py-1 pr-2 whitespace-pre-wrap text-red-800">{show(s.current[f])}</td>
              <td className="py-1 whitespace-pre-wrap text-green-800">{show(s.patch[f])}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <TextArea
        aria-label={t("collab.moderation.comment")}
        placeholder={t("collab.moderation.comment")}
        rows={2}
        value={comment}
        onChange={(e) => setComment(e.target.value)}
      />
      <ErrorAlert error={review.error} />
      <div className="flex gap-2">
        <Button
          busy={review.isPending}
          onClick={() =>
            review.mutate({ id: s.id, decision: "approve", comment: comment || undefined })
          }
        >
          {t("collab.moderation.approve")}
        </Button>
        <Button
          variant="secondary"
          busy={review.isPending}
          onClick={() =>
            review.mutate({ id: s.id, decision: "reject", comment: comment || undefined })
          }
        >
          {t("collab.moderation.reject")}
        </Button>
      </div>
    </Card>
  );
}
