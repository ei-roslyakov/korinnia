import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router";

import { Badge, Button, ErrorAlert, Field, Input, PageHeader, Spinner } from "@/components/ui";
import { useSaveStory, useStory, useStoryAction } from "@/features/collab/api";
import { clearDraft, fromPartialDate, toPayload } from "@/features/builder/helpers";
import { MarkdownEditor } from "@/features/builder/MarkdownEditor";
import { PartialDateInput } from "@/features/builder/PartialDateInput";
import { MediaAttach } from "@/features/media/MediaAttach";
import { PersonCombobox } from "@/features/person/PersonCombobox";
import { useTree } from "@/features/tree/api";
import type { PartialDateInput as DateValue, MediaItem, Story } from "@/lib/genealogy";
import { atLeast } from "@/lib/types";

export function StoryEditorPage() {
  const { treeId = "", storyId } = useParams();
  const story = useStory(treeId, storyId);
  const tree = useTree(treeId);
  if (tree.isPending || (storyId && story.isPending)) return <Spinner />;
  if (tree.error || story.error) return <ErrorAlert error={tree.error ?? story.error} />;
  return (
    <StoryForm
      key={story.data?.updated_at ?? "new"}
      treeId={treeId}
      story={story.data ?? null}
      isEditor={atLeast(tree.data.my_role, "editor")}
    />
  );
}

function StoryForm({
  treeId,
  story,
  isEditor,
}: {
  treeId: string;
  story: Story | null;
  isEditor: boolean;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const save = useSaveStory(treeId);
  const action = useStoryAction(treeId);
  const [title, setTitle] = useState(story?.title ?? "");
  const [narrator, setNarrator] = useState(story?.narrator ?? "");
  const [date, setDate] = useState<DateValue | null>(fromPartialDate(story?.date));
  const [body, setBody] = useState(story?.body ?? "");
  const [people, setPeople] = useState(
    story?.persons.map((p) => ({ id: p.id, name: p.display_name })) ?? [],
  );
  const [media, setMedia] = useState<MediaItem[]>(story?.media ?? []);
  const draftKey = `korinnia.draft.story.${story?.id ?? "new"}`;

  const submit = async (then: "stay" | "submit" | "publish") => {
    const saved = await save.mutateAsync({
      id: story?.id,
      title: title.trim(),
      narrator: narrator.trim() || null,
      date: toPayload(date),
      body,
      person_ids: people.map((p) => p.id),
      media_ids: media.map((m) => m.id),
      ...(story ? {} : { status: then === "publish" ? "published" : "draft" }),
    });
    clearDraft(draftKey);
    if (then === "submit" && saved.status === "draft")
      await action.mutateAsync({ id: saved.id, action: "submit" });
    if (then === "publish" && story && saved.status !== "published")
      await action.mutateAsync({ id: saved.id, action: "publish" });
    void navigate(`/trees/${treeId}/stories/${saved.id}`);
  };

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Link
        to={story ? `/trees/${treeId}/stories/${story.id}` : `/trees/${treeId}/stories`}
        className="text-leaf-700 text-sm underline"
      >
        ← {t("common.back")}
      </Link>
      <PageHeader
        title={story ? story.title : t("collab.story.new")}
        actions={story && <Badge>{t(`collab.storyStatus.${story.status}`)}</Badge>}
      />
      <Field label={t("builder.events.title")}>
        {(id) => (
          <Input
            id={id}
            required
            maxLength={300}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        )}
      </Field>
      <Field label={t("collab.story.narrator")} hint={t("collab.story.narratorHint")}>
        {(id) => <Input id={id} value={narrator} onChange={(e) => setNarrator(e.target.value)} />}
      </Field>
      <PartialDateInput label={t("collab.story.when")} value={date} onChange={setDate} />
      <div className="space-y-2">
        <span className="block text-sm font-medium">{t("collab.story.about")}</span>
        <div className="flex flex-wrap gap-2">
          {people.map((p) => (
            <span
              key={p.id}
              className="bg-bark-100 flex items-center gap-1 rounded-full px-2 py-0.5 text-sm"
            >
              {p.name}
              <button
                type="button"
                aria-label={t("common.remove")}
                onClick={() => setPeople(people.filter((x) => x.id !== p.id))}
              >
                ✕
              </button>
            </span>
          ))}
        </div>
        <PersonCombobox
          treeId={treeId}
          label={t("collab.story.addPerson")}
          excludeIds={people.map((p) => p.id)}
          onSelect={(p) => setPeople([...people, { id: p.id, name: p.display_name }])}
        />
      </div>
      <MarkdownEditor
        label={t("collab.story.body")}
        value={body}
        onChange={setBody}
        draftKey={draftKey}
        rows={16}
      />
      <MediaAttach
        treeId={treeId}
        label={t("collab.story.media")}
        value={media}
        onChange={setMedia}
        canUpload={isEditor}
      />
      <ErrorAlert error={save.error ?? action.error} />
      <div className="flex flex-wrap gap-2">
        <Button
          variant="secondary"
          busy={save.isPending}
          disabled={!title.trim()}
          onClick={() => void submit("stay")}
        >
          {t("collab.story.saveDraft")}
        </Button>
        {!isEditor && (
          <Button
            busy={save.isPending}
            disabled={!title.trim()}
            onClick={() => void submit("submit")}
          >
            {t("collab.story.submit")}
          </Button>
        )}
        {isEditor && (
          <Button
            busy={save.isPending}
            disabled={!title.trim()}
            onClick={() => void submit("publish")}
          >
            {t("collab.story.publish")}
          </Button>
        )}
      </div>
      {!isEditor && <p className="text-bark-700 text-xs">{t("collab.story.moderationNote")}</p>}
    </div>
  );
}
