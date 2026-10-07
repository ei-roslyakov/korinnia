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
  const role = tree.data.my_role;
  const isEditor = atLeast(role, "editor");
  const isAuthor = s.author?.id === me.data?.id;

  return (
    <article className="mx-auto max-w-3xl space-y-4">
      <Link
        to={`/trees/${treeId}/stories`}
        className="text-leaf-700 text-sm underline print:hidden"
      >
        ← {t("collab.stories")}
      </Link>
      <header className="space-y-1">
        <h1 className="font-serif text-3xl font-semibold">{s.title}</h1>
        <div className="text-bark-700 text-sm">
          {[
            formatPartialDate(s.date, t, i18n.language),
            s.narrator && t("collab.story.toldBy", { name: s.narrator }),
            s.author && t("collab.story.writtenBy", { name: s.author.display_name }),
          ]
            .filter(Boolean)
            .join(" · ")}
        </div>
        {s.status !== "published" && (
          <Badge tone="amber">{t(`collab.storyStatus.${s.status}`)}</Badge>
        )}
        {s.persons.length > 0 && (
          <div className="flex flex-wrap gap-2 text-sm">
            {t("collab.story.about")}:
            {s.persons.map((p) => (
              <Link
                key={p.id}
                to={`/trees/${treeId}/people/${p.id}`}
                className="text-leaf-700 underline"
              >
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
            className="border-bark-100 hover:bg-bark-50 rounded-md border bg-white px-3 py-1.5 text-sm"
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
      <Markdown className="font-serif text-lg">{s.body}</Markdown>
      <MediaSections
        media={s.media}
        personLink={(id) => `/trees/${treeId}/people/${id}`}
        comments={{ treeId, role }}
        Section={({ title, children }) => (
          <section className="space-y-2">
            <h2 className="text-bark-700 text-xs font-semibold tracking-wide uppercase">{title}</h2>
            {children}
          </section>
        )}
      />
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
