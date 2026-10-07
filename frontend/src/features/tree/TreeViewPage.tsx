import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams, useSearchParams } from "react-router";

import { Button, ErrorAlert, Select, Spinner } from "@/components/ui";
import { AddRelativeDialog } from "@/features/builder/AddRelativeDialog";
import { useResetLayout, useSaveLayoutOffset } from "@/features/builder/api";
import { useModerationCounts } from "@/features/collab/api";
import { useGraph, usePerson } from "@/features/person/api";
import type { RelativeRelation } from "@/lib/genealogy";
import { PersonView } from "@/features/person/PersonView";
import { atLeast, type Role } from "@/lib/types";

import { useTree } from "./api";
import { TreeNav } from "./TreeNav";
import { defaultFocus, focusSet, indexRelations } from "./canvas/familyGraph";
import { TreeCanvas, type CenterRequest } from "./canvas/TreeCanvas";
import { SearchBox } from "./SearchBox";

/** Trees larger than this open in focus mode instead of showing everyone. */
const FOCUS_THRESHOLD = 150;
const GENERATION_CHOICES = [1, 2, 3, 4, 5, 6];

export function TreeViewPage() {
  const { t } = useTranslation();
  const { treeId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const tree = useTree(treeId);
  const graph = useGraph(treeId);
  const [center, setCenter] = useState<CenterRequest | null>(null);
  const [adding, setAdding] = useState<{
    relativeId: string | null;
    relation: RelativeRelation | null;
  } | null>(null);
  const saveOffset = useSaveLayoutOffset(treeId);
  const resetLayout = useResetLayout(treeId);
  const moderation = useModerationCounts(
    treeId,
    tree.data ? atLeast(tree.data.my_role, "editor") : false,
  );
  const pending = (moderation.data?.suggestions ?? 0) + (moderation.data?.stories ?? 0);

  const personId = params.get("person");
  const generations = Number(params.get("gen") ?? 3) || 3;
  const showAll = params.get("all") === "1";
  const rel = useMemo(() => (graph.data ? indexRelations(graph.data) : null), [graph.data]);

  const focusId = useMemo(() => {
    if (!graph.data || !rel) return null;
    const explicit = params.get("focus");
    if (explicit && graph.data.persons.some((p) => p.id === explicit)) return explicit;
    if (showAll || graph.data.persons.length <= FOCUS_THRESHOLD) return null;
    return defaultFocus(graph.data, rel);
  }, [graph.data, rel, params, showAll]);

  const included = useMemo(() => {
    if (!graph.data || !rel) return new Set<string>();
    if (focusId) return focusSet(rel, focusId, generations, generations);
    return new Set(graph.data.persons.map((p) => p.id));
  }, [graph.data, rel, focusId, generations]);

  const update = (changes: Record<string, string | null>) => {
    const next = new URLSearchParams(params);
    for (const [k, v] of Object.entries(changes)) {
      if (v === null) next.delete(k);
      else next.set(k, v);
    }
    setParams(next, { replace: true });
  };

  const personLink = (id: string) => {
    const next = new URLSearchParams(params);
    next.set("person", id);
    return `/trees/${treeId}?${next.toString()}`;
  };

  const goTo = (id: string) => {
    const changes: Record<string, string | null> = { person: id };
    if (focusId && !included.has(id)) changes.focus = id;
    update(changes);
    setCenter({ personId: id, nonce: Date.now() });
  };

  if (tree.isPending || graph.isPending) {
    return (
      <div className="flex flex-1 items-center justify-center">
        <Spinner />
      </div>
    );
  }
  if (tree.error || graph.error) {
    return (
      <div className="p-4">
        <ErrorAlert error={tree.error ?? graph.error} />
      </div>
    );
  }
  const canEdit = atLeast(tree.data.my_role, "editor");
  const builder = canEdit && params.get("mode") === "edit";
  const count = graph.data.persons.length;

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="border-bark-100 flex flex-wrap items-center gap-x-4 gap-y-2 border-b bg-white px-4 py-2">
        <h1 className="font-serif text-lg font-semibold">{tree.data.name}</h1>
        <span className="text-bark-700 text-xs">{t("canvas.persons", { count })}</span>
        {count > 0 && <SearchBox treeId={treeId} onSelect={(p) => goTo(p.id)} />}
        {count > 0 && (
          <div className="flex items-center gap-2 text-sm">
            <div
              className="border-bark-100 inline-flex overflow-hidden rounded-md border"
              role="group"
            >
              <button
                type="button"
                aria-pressed={!focusId}
                className={`px-2 py-1 ${!focusId ? "bg-leaf-700 text-white" : "bg-white"}`}
                onClick={() => update({ all: "1", focus: null })}
              >
                {t("canvas.wholeTree")}
              </button>
              <button
                type="button"
                aria-pressed={Boolean(focusId)}
                className={`px-2 py-1 ${focusId ? "bg-leaf-700 text-white" : "bg-white"}`}
                onClick={() =>
                  update({
                    all: null,
                    focus: personId ?? focusId ?? (rel ? defaultFocus(graph.data, rel) : null),
                  })
                }
              >
                {t("canvas.focus")}
              </button>
            </div>
            {focusId && (
              <Select
                aria-label={t("canvas.generations")}
                className="w-auto py-1"
                value={generations}
                onChange={(e) => update({ gen: e.target.value })}
              >
                {GENERATION_CHOICES.map((g) => (
                  <option key={g} value={g}>
                    {t("canvas.generations")}: {g}
                  </option>
                ))}
              </Select>
            )}
          </div>
        )}
        {canEdit && (
          <div
            className="border-bark-100 inline-flex overflow-hidden rounded-md border text-sm"
            role="group"
          >
            {(["view", "edit"] as const).map((m) => (
              <button
                key={m}
                type="button"
                aria-pressed={(m === "edit") === builder}
                className={`px-2 py-1 ${(m === "edit") === builder ? "bg-leaf-700 text-white" : "bg-white"}`}
                onClick={() => update({ mode: m === "edit" ? "edit" : null })}
              >
                {t(`builder.mode.${m}`)}
              </button>
            ))}
          </div>
        )}
        {builder && (
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <Button onClick={() => setAdding({ relativeId: null, relation: null })}>
              + {t("builder.addPerson")}
            </Button>
            <Link to={`/trees/${treeId}/trash`} className="text-leaf-700 hover:underline">
              {t("builder.trash.title")}
            </Link>
            {Object.keys(graph.data.layout_offsets ?? {}).length > 0 && (
              <Button
                variant="ghost"
                busy={resetLayout.isPending}
                onClick={() =>
                  window.confirm(t("builder.resetLayoutConfirm")) && resetLayout.mutate()
                }
              >
                {t("builder.resetLayout")}
              </Button>
            )}
          </div>
        )}
        <TreeNav treeId={treeId} role={tree.data.my_role} pending={pending} />
      </div>

      <div className="relative min-h-0 flex-1">
        {count === 0 ? (
          <div className="text-bark-700 mx-auto max-w-lg p-8 text-center">
            <p className="font-medium">{t("canvas.empty")}</p>
            <p className="mt-2 text-sm">{t("canvas.emptyHint")}</p>
          </div>
        ) : (
          <TreeCanvas
            treeId={treeId}
            graph={graph.data}
            included={included}
            focusMode={Boolean(focusId)}
            selectedId={personId}
            center={center}
            onSelectPerson={(id) => update({ person: id })}
            builder={builder}
            onAddRelative={(relativeId, relation) => setAdding({ relativeId, relation })}
            onMoved={(personId, dx, dy) => saveOffset.mutate({ personId, dx, dy })}
          />
        )}
        {personId && (
          <PersonPanel
            treeId={treeId}
            personId={personId}
            showWarnings={canEdit}
            editLink={canEdit ? `/trees/${treeId}/people/${personId}/edit` : null}
            role={tree.data.my_role}
            personLink={personLink}
            onClose={() => update({ person: null })}
            onFocus={() => {
              update({ focus: personId, all: null });
              setCenter({ personId, nonce: Date.now() });
            }}
          />
        )}
        {adding && (
          <AddRelativeDialog
            treeId={treeId}
            relativeId={adding.relativeId}
            relation={adding.relation}
            onClose={() => setAdding(null)}
            onCreated={(person) => {
              setAdding(null);
              const changes: Record<string, string | null> = { person: person.id };
              if (focusId) changes.focus = person.id;
              update(changes);
              setCenter({ personId: person.id, nonce: Date.now() });
            }}
          />
        )}
      </div>
    </div>
  );
}

function PersonPanel({
  treeId,
  personId,
  showWarnings,
  editLink,
  personLink,
  onClose,
  onFocus,
  role,
}: {
  treeId: string;
  personId: string;
  showWarnings: boolean;
  role: Role;
  editLink: string | null;
  personLink: (id: string) => string;
  onClose: () => void;
  onFocus: () => void;
}) {
  const { t } = useTranslation();
  const person = usePerson(treeId, personId);
  return (
    <aside
      aria-label={person.data?.display_name}
      className="border-bark-100 absolute inset-y-0 right-0 z-10 flex w-full flex-col border-l bg-white shadow-xl sm:w-[28rem]"
    >
      <div className="border-bark-100 flex items-center justify-between gap-2 border-b px-4 py-2">
        <div className="flex gap-2">
          <Button variant="secondary" onClick={onFocus}>
            {t("canvas.focusHere")}
          </Button>
          <Link
            to={`/trees/${treeId}/people/${personId}`}
            className="text-leaf-700 hover:bg-bark-50 inline-flex items-center rounded-md px-3 py-1.5 text-sm"
          >
            {t("canvas.openPage")}
          </Link>
          {editLink && (
            <Link
              to={editLink}
              className="bg-leaf-700 hover:bg-leaf-600 inline-flex items-center rounded-md px-3 py-1.5 text-sm text-white"
            >
              {t("builder.edit")}
            </Link>
          )}
        </div>
        <Button variant="ghost" onClick={onClose} aria-label={t("canvas.close")}>
          ✕
        </Button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        {person.isPending && <Spinner />}
        <ErrorAlert error={person.error} />
        {person.data && (
          <PersonView
            person={person.data}
            personLink={personLink}
            showWarnings={showWarnings}
            treeId={treeId}
            role={role}
          />
        )}
      </div>
    </aside>
  );
}
