import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams, useSearchParams } from "react-router";

import { Button, ErrorAlert, Select, Spinner } from "@/components/ui";
import { AddRelativeDialog } from "@/features/builder/AddRelativeDialog";
import { DeletePersonDialog } from "@/features/builder/DeletePersonDialog";
import { useResetLayout, useSaveLayoutOffsets } from "@/features/builder/api";
import { useModerationCounts } from "@/features/collab/api";
import { useGraph, usePerson } from "@/features/person/api";
import type { RelativeRelation } from "@/lib/genealogy";
import { PersonView } from "@/features/person/PersonView";
import { atLeast, type Role } from "@/lib/types";

import { useTree } from "./api";
import { TreeActions } from "./TreeActions";
import { TreeNav } from "./TreeNav";
import { defaultFocus, focusSet, indexRelations } from "./canvas/familyGraph";
import { TreeCanvas, type CenterRequest } from "./canvas/TreeCanvas";
import { SearchBox } from "./SearchBox";
import { EmptyState } from "@/components/EmptyState";
import { HeaderSelect } from "@/components/HeaderSelect";
import { readTreeStyle, saveTreeStyle, TREE_STYLES, type TreeStyle } from "./canvas/treeStyle";

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
  const saveOffsets = useSaveLayoutOffsets(treeId);
  const [treeStyle, setTreeStyle] = useState<TreeStyle>(readTreeStyle);
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
      <div className="border-bark-100 bg-surface flex flex-wrap items-center gap-x-4 gap-y-2 border-b px-4 py-2">
        <h1 className="font-serif text-lg font-semibold">{tree.data.name}</h1>
        <span className="text-bark-700 text-xs">{t("canvas.persons", { count })}</span>
        {count > 0 && <SearchBox treeId={treeId} onSelect={(p) => goTo(p.id)} />}
        {count > 0 && (
          <div className="flex items-center gap-2 text-sm">
            <div
              className="border-bark-100 inline-flex shrink-0 overflow-hidden rounded-md border"
              role="group"
            >
              <button
                type="button"
                aria-pressed={!focusId}
                className={`px-2 py-1 whitespace-nowrap ${!focusId ? "bg-leaf-700 text-on-leaf" : "bg-surface"}`}
                onClick={() => update({ all: "1", focus: null })}
              >
                {t("canvas.wholeTree")}
              </button>
              <button
                type="button"
                aria-pressed={Boolean(focusId)}
                className={`px-2 py-1 whitespace-nowrap ${focusId ? "bg-leaf-700 text-on-leaf" : "bg-surface"}`}
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
            className="border-bark-100 inline-flex shrink-0 overflow-hidden rounded-md border text-sm"
            role="group"
          >
            {(["view", "edit"] as const).map((m) => (
              <button
                key={m}
                type="button"
                aria-pressed={(m === "edit") === builder}
                className={`px-2 py-1 whitespace-nowrap ${(m === "edit") === builder ? "bg-leaf-700 text-on-leaf" : "bg-surface"}`}
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
            <Link to={`/trees/${treeId}/import`} className="text-leaf-700 hover:underline">
              {t("imports.link")}
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
            <TreeActions tree={tree.data} leaveTo="/" />
          </div>
        )}
        {count > 0 && (
          <label className="text-bark-700 flex items-center gap-1.5 text-sm">
            <span>{t("canvas.treeStyle.label")}</span>
            <HeaderSelect
              aria-label={t("canvas.treeStyle.label")}
              value={treeStyle}
              onChange={(e) => {
                const style = e.target.value as TreeStyle;
                setTreeStyle(style);
                saveTreeStyle(style);
              }}
            >
              {TREE_STYLES.map((s) => (
                <option key={s} value={s}>
                  {t(`canvas.treeStyle.${s}`)}
                </option>
              ))}
            </HeaderSelect>
          </label>
        )}
        <TreeNav treeId={treeId} role={tree.data.my_role} pending={pending} />
      </div>

      <div className="relative min-h-0 flex-1">
        {count === 0 ? (
          <div className="mx-auto max-w-lg p-8">
            <EmptyState
              title={t("canvas.empty")}
              hint={canEdit ? t("canvas.emptyHintEditor") : t("canvas.emptyHint")}
              action={
                canEdit && (
                  <div className="flex flex-col items-center gap-2">
                    <Button onClick={() => setAdding({ relativeId: null, relation: null })}>
                      + {t("builder.addPerson")}
                    </Button>
                    <Link
                      to={`/trees/${treeId}/import`}
                      className="text-leaf-700 text-sm underline"
                    >
                      {t("imports.orImport")}
                    </Link>
                  </div>
                )
              }
            />
          </div>
        ) : (
          <TreeCanvas
            treeId={treeId}
            treeStyle={treeStyle}
            graph={graph.data}
            included={included}
            focusMode={Boolean(focusId)}
            selectedId={personId}
            center={center}
            onSelectPerson={(id) => update({ person: id })}
            builder={builder}
            onAddRelative={(relativeId, relation) => setAdding({ relativeId, relation })}
            onMoved={(offsets) => saveOffsets.mutate(offsets)}
            exportTitle={tree.data.name}
          />
        )}
        {personId && (
          <PersonPanel
            treeId={treeId}
            personId={personId}
            showWarnings={canEdit}
            editLink={canEdit ? `/trees/${treeId}/people/${personId}/edit` : null}
            canDelete={builder}
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
  canDelete,
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
  canDelete: boolean;
  personLink: (id: string) => string;
  onClose: () => void;
  onFocus: () => void;
}) {
  const { t } = useTranslation();
  const person = usePerson(treeId, personId);
  const [deleting, setDeleting] = useState(false);
  return (
    <aside
      aria-label={person.data?.display_name}
      className="border-bark-100 bg-surface absolute inset-y-0 right-0 z-10 flex w-full flex-col border-l shadow-xl motion-safe:animate-[panel-in_200ms_ease-out] sm:w-[28rem]"
    >
      <div className="border-bark-100 flex items-center justify-between gap-2 border-b px-4 py-2">
        <div className="flex flex-wrap gap-2">
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
              className="bg-leaf-700 hover:bg-leaf-600 text-on-leaf inline-flex items-center rounded-md px-3 py-1.5 text-sm"
            >
              {t("builder.edit")}
            </Link>
          )}
          {canDelete && (
            <Button
              variant="ghost"
              className="text-red-700"
              title={t("builder.delete.confirm")}
              onClick={() => setDeleting(true)}
            >
              {t("common.delete")}
            </Button>
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
      {deleting && (
        <DeletePersonDialog
          treeId={treeId}
          personId={personId}
          onClose={() => setDeleting(false)}
          onDeleted={onClose}
        />
      )}
    </aside>
  );
}
