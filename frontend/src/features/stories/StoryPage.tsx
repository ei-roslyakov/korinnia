import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router";

import { Markdown } from "@/components/Markdown";
import { Alert, Badge, Button, ErrorAlert, Spinner, TextArea } from "@/components/ui";
import { useDeleteStory, useStory, useStoryAction } from "@/features/collab/api";
import { CommentsThread } from "@/features/collab/CommentsThread";
import { useMe } from "@/features/auth/api";
import { MediaSections } from "@/features/media/MediaSections";
import { useTree } from "@/features/tree/api";
import { formatPartialDate } from "@/lib/dates";
import { atLeast } from "@/lib/types";
import { Avatar } from "@/features/person/Avatar";
import { isVisual } from "@/lib/genealogy";

import { RecipeView } from "./RecipeView";

export function StoryPage() {
  const { t, i18n } = useTranslation();
  const { treeId = "", storyId } = useParams();
  const navigate = useNavigate();
  const me = useMe();
  const tree = useTree(treeId);
  const story = useStory(treeId, storyId);
  const action = useStoryAction(treeId);
  const del = useDeleteStory(treeId);
  const [returning, setReturning] = useState(false);
  const [comment, setComment] = useState("");

  if (story.isPending || tree.isPending) return <Spinner />;
  if (story.error || tree.error) return <ErrorAlert error={story.error ?? tree.error} />;
  const s = story.data;
  const cover = s.media.find((m) => isVisual(m) && m.urls.web);
  const role = tree.data.my_role;
  const isEditor = atLeast(role, "editor");
  const isAuthor = s.author?.id === me.data?.id;

  return (
    <article className={`mx-auto max-w-3xl space-y-4 ${s.kind === "recipe" ? "recipe-page" : ""}`}>
      <Link
        to={`/trees/${treeId}/stories`}
        className="text-leaf-700 text-sm underline print:hidden"
      >
        ← {t("collab.stories")}
      </Link>
      {cover && (
        <figure className="overflow-hidden rounded-lg">
          <img
            src={cover.urls.web}
            alt={cover.title ?? ""}
            className="max-h-96 w-full object-cover sepia-[15%]"
          />
          {cover.title && (
            <figcaption className="text-bark-700 mt-1 text-xs italic">{cover.title}</figcaption>
          )}
        </figure>
      )}
      <header className="space-y-2">
        <h1 className="font-serif text-4xl leading-tight font-semibold">{s.title}</h1>
        <div className="text-bark-700 text-sm">
          {[
            s.kind && s.kind !== "story" && t(`recipes.kinds.${s.kind}`),
            s.kind === "tradition" && s.occasion,
            formatPartialDate(s.date, t, i18n.language),
            s.narrator &&
              t(s.kind === "recipe" ? "recipes.from" : "collab.story.toldBy", {
                name: s.narrator,
              }),
            s.author && t("collab.story.writtenBy", { name: s.author.display_name }),
            s.kind !== "recipe" && t("collab.story.readingTime", { count: s.reading_minutes ?? 1 }),
          ]
            .filter(Boolean)
            .join(" · ")}
        </div>
        {s.status !== "published" && (
          <Badge tone="amber">{t(`collab.storyStatus.${s.status}`)}</Badge>
        )}
        {s.persons.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="text-bark-700">{t("collab.story.about")}:</span>
            {s.persons.map((p) => (
              <Link
                key={p.id}
                to={`/trees/${treeId}/people/${p.id}`}
                className="border-bark-100 bg-surface text-leaf-700 hover:border-leaf-600 flex items-center gap-2 rounded-full border py-0.5 pr-3 pl-0.5"
              >
                <Avatar name={p.display_name} gender={p.gender} url={p.avatar_url} size="sm" />
                {p.display_name}
              </Link>
            ))}
          </div>
        )}
      </header>
      {s.review_comment && s.status === "draft" && (
        <Alert kind="info">
          {t("collab.story.returned")}: {s.review_comment}
        </Alert>
      )}
      <ErrorAlert error={action.error ?? del.error} />
      <div className="flex flex-wrap gap-2 print:hidden">
        {s.can_edit && (
          <Link
            to={`/trees/${treeId}/stories/${s.id}/edit`}
            className="border-bark-100 hover:bg-bark-50 bg-surface rounded-md border px-3 py-1.5 text-sm"
          >
            {t("builder.edit")}
          </Link>
        )}
        {s.status === "draft" && (isAuthor || isEditor) && !isEditor && (
          <Button onClick={() => action.mutate({ id: s.id, action: "submit" })}>
            {t("collab.story.submit")}
          </Button>
        )}
        {isEditor && s.status !== "published" && (
          <Button onClick={() => action.mutate({ id: s.id, action: "publish" })}>
            {t("collab.story.publish")}
          </Button>
        )}
        {isEditor && s.status === "pending_review" && (
          <Button variant="secondary" onClick={() => setReturning(true)}>
            {t("collab.story.return")}
          </Button>
        )}
        {s.kind === "recipe" && (
          <Button variant="secondary" onClick={() => window.print()}>
            {t("recipes.print")}
          </Button>
        )}
        {s.can_edit && (
          <Button
            variant="ghost"
            className="text-red-700"
            onClick={() =>
              window.confirm(t("collab.story.confirmDelete")) &&
              del.mutate(s.id, { onSuccess: () => void navigate(`/trees/${treeId}/stories`) })
            }
          >
            {t("common.delete")}
          </Button>
        )}
      </div>
      {returning && (
        <div className="space-y-2">
          <TextArea
            aria-label={t("collab.story.returnComment")}
            placeholder={t("collab.story.returnComment")}
            value={comment}
            onChange={(e) => setComment(e.target.value)}
          />
          <Button
            onClick={() =>
              action.mutate(
                { id: s.id, action: "return", comment },
                { onSuccess: () => setReturning(false) },
              )
            }
          >
            {t("collab.story.return")}
          </Button>
        </div>
      )}
      {s.kind === "recipe" && s.recipe && <RecipeView recipe={s.recipe} occasion={s.occasion} />}
      {s.kind === "recipe" && s.body.trim() && (
        <h2 className="font-serif text-lg font-semibold">{t("recipes.storyBehind")}</h2>
      )}
      <Markdown className="[&>p:first-of-type]:first-letter:text-leaf-700 font-serif text-lg [&>p:first-of-type]:first-letter:float-left [&>p:first-of-type]:first-letter:mt-1 [&>p:first-of-type]:first-letter:mr-2 [&>p:first-of-type]:first-letter:font-serif [&>p:first-of-type]:first-letter:text-6xl [&>p:first-of-type]:first-letter:leading-[0.8] [&>p:first-of-type]:first-letter:font-semibold">
        {s.body}
      </Markdown>
      <div className="print:hidden">
        <MediaSections
          media={s.media}
          personLink={(id) => `/trees/${treeId}/people/${id}`}
          comments={{ treeId, role }}
          Section={({ title, children }) => (
            <section className="space-y-2">
              <h2 className="text-bark-700 text-xs font-semibold tracking-wide uppercase">
                {title}
              </h2>
              {children}
            </section>
          )}
        />
      </div>
      <section className="space-y-2 print:hidden">
        <h2 className="text-bark-700 text-xs font-semibold tracking-wide uppercase">
          {t("collab.comments.title")}
        </h2>
        <CommentsThread
          treeId={treeId}
          entityType="story"
          entityId={s.id}
          canWrite={atLeast(role, "contributor")}
          canModerate={isEditor}
        />
      </section>
    </article>
  );
}
