import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";

import {
  Badge,
  Button,
  ErrorAlert,
  Field,
  Input,
  PageHeader,
  Select,
  Spinner,
} from "@/components/ui";
import { useSaveStory, useStory, useStoryAction } from "@/features/collab/api";
import { clearDraft, fromPartialDate, toPayload } from "@/features/builder/helpers";
import { MarkdownEditor } from "@/features/builder/MarkdownEditor";
import { PartialDateInput } from "@/features/builder/PartialDateInput";
import { MediaAttach } from "@/features/media/MediaAttach";
import { usePerson } from "@/features/person/api";
import { PersonCombobox } from "@/features/person/PersonCombobox";
import { useTree } from "@/features/tree/api";
import type {
  PartialDateInput as DateValue,
  MediaItem,
  Recipe,
  Story,
  StoryKind,
} from "@/lib/genealogy";
import { atLeast } from "@/lib/types";
import { useToast } from "@/lib/toast";

import { cleanRecipe, EMPTY_RECIPE } from "./recipe";
import { RecipeFields } from "./RecipeFields";
import { RecipeView } from "./RecipeView";

const KINDS: StoryKind[] = ["story", "recipe", "tradition"];

export function StoryEditorPage() {
  const { treeId = "", storyId } = useParams();
  const [params] = useSearchParams();
  const story = useStory(treeId, storyId);
  const tree = useTree(treeId);
  // "Add a recipe" on a person's page: /stories/new?kind=recipe&person=<id>
  const personId = storyId ? null : params.get("person");
  const person = usePerson(treeId, personId);
  if (tree.isPending || (storyId && story.isPending) || (personId && person.isPending))
    return <Spinner />;
  if (tree.error || story.error) return <ErrorAlert error={tree.error ?? story.error} />;
  const asked = params.get("kind") as StoryKind | null;
  return (
    <StoryForm
      key={story.data?.updated_at ?? "new"}
      treeId={treeId}
      story={story.data ?? null}
      isEditor={atLeast(tree.data.my_role, "editor")}
      initialKind={asked && KINDS.includes(asked) ? asked : "story"}
      initialPerson={person.data ? { id: person.data.id, name: person.data.display_name } : null}
    />
  );
}

function StoryForm({
  treeId,
  story,
  isEditor,
  initialKind,
  initialPerson,
}: {
  treeId: string;
  story: Story | null;
  isEditor: boolean;
  initialKind: StoryKind;
  initialPerson: { id: string; name: string } | null;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const save = useSaveStory(treeId);
  const toast = useToast();
  const action = useStoryAction(treeId);
  const [title, setTitle] = useState(story?.title ?? "");
  const [narrator, setNarrator] = useState(story?.narrator ?? "");
  const [date, setDate] = useState<DateValue | null>(fromPartialDate(story?.date));
  const [body, setBody] = useState(story?.body ?? "");
  const [people, setPeople] = useState(
    story?.persons.map((p) => ({ id: p.id, name: p.display_name })) ??
      (initialPerson ? [initialPerson] : []),
  );
  const [kind, setKind] = useState<StoryKind>(story?.kind ?? initialKind);
  const [occasion, setOccasion] = useState(story?.occasion ?? "");
  const [recipe, setRecipe] = useState<Recipe>(story?.recipe ?? EMPTY_RECIPE);
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
      kind,
      occasion: kind === "story" ? null : occasion.trim() || null,
      recipe: kind === "recipe" ? cleanRecipe(recipe) : null,
      ...(story ? {} : { status: then === "publish" ? "published" : "draft" }),
    });
    clearDraft(draftKey);
    toast(t("common.saved"));
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
        title={story ? story.title : t(`recipes.new.${kind}`)}
        actions={story && <Badge>{t(`collab.storyStatus.${story.status}`)}</Badge>}
      />
      <Field label={t("recipes.kind")}>
        {(id) => (
          <Select id={id} value={kind} onChange={(e) => setKind(e.target.value as StoryKind)}>
            {KINDS.map((k) => (
              <option key={k} value={k}>
                {t(`recipes.kinds.${k}`)}
              </option>
            ))}
          </Select>
        )}
      </Field>
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
      {kind !== "story" && (
        <Field label={t("recipes.occasion")} hint={t("recipes.occasionHint")}>
          {(id) => (
            <Input
              id={id}
              maxLength={200}
              value={occasion}
              onChange={(e) => setOccasion(e.target.value)}
            />
          )}
        </Field>
      )}
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
      {kind === "recipe" && (
        <>
          <RecipeFields value={recipe} onChange={setRecipe} />
          <section className="border-bark-100 bg-surface space-y-2 rounded-lg border p-4">
            <h2 className="text-bark-700 text-xs font-semibold tracking-wide uppercase">
              {t("recipes.preview")}
            </h2>
            <RecipeView recipe={recipe} occasion={occasion} />
          </section>
        </>
      )}
      <MarkdownEditor
        label={t(kind === "recipe" ? "recipes.storyBehind" : "collab.story.body")}
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
