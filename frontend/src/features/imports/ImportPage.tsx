import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";

import { Alert, Badge, Button, Card, ErrorAlert, PageHeader, Spinner } from "@/components/ui";
import { useDeleteTreeById } from "@/features/tree/api";
import { useFormatDate } from "@/lib/hooks";

import {
  BUSY,
  type GedcomImport,
  type ImportCounts,
  type ImportStatus,
  type ImportWarning,
  useImport,
  useImportAction,
  useImports,
  useUploadGedcom,
} from "./api";

const TONE: Record<ImportStatus, "neutral" | "green" | "red" | "amber"> = {
  analyzing: "amber",
  ready: "amber",
  importing: "amber",
  done: "green",
  failed: "red",
  undoing: "amber",
  undone: "neutral",
  cancelled: "neutral",
};

/** GEDCOM import: upload a file, review what is in it, choose duplicates, import, undo. */
export function ImportPage() {
  const { t } = useTranslation();
  const { treeId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const id = params.get("import");
  const imports = useImports(treeId);
  const current = useImport(treeId, id);
  const upload = useUploadGedcom(treeId);
  const input = useRef<HTMLInputElement>(null);
  const select = (importId: string | null) =>
    setParams(importId ? { import: importId } : {}, { replace: true });

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <Link to={`/trees/${treeId}?mode=edit`} className="text-leaf-700 text-sm underline">
        ← {t("person.backToTree")}
      </Link>
      <PageHeader title={t("imports.title")} />
      <Card className="space-y-3">
        <p className="text-bark-700 text-sm">{t("imports.intro")}</p>
        <input
          ref={input}
          type="file"
          accept=".ged,.GED,text/plain"
          className="hidden"
          aria-label={t("imports.choose")}
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (file) upload.mutate(file, { onSuccess: (imp) => select(imp.id) });
          }}
        />
        <div className="flex flex-wrap items-center gap-3">
          <Button busy={upload.isPending} onClick={() => input.current?.click()}>
            {t("imports.choose")}
          </Button>
          <span className="text-bark-700 text-xs">{t("imports.formats")}</span>
        </div>
        <ErrorAlert error={upload.error} />
      </Card>

      {id && current.isPending && <Spinner />}
      <ErrorAlert error={current.error} />
      {current.data && (
        <ImportDetail treeId={treeId} imp={current.data} newTree={params.get("new") === "1"} />
      )}

      {imports.data && imports.data.length > 0 && (
        <Card>
          <h2 className="mb-2 font-semibold">{t("imports.history")}</h2>
          <ul className="divide-bark-100 divide-y text-sm">
            {imports.data.map((imp) => (
              <ImportRow
                key={imp.id}
                imp={imp}
                active={imp.id === id}
                onOpen={() => select(imp.id)}
              />
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}

function ImportRow({
  imp,
  active,
  onOpen,
}: {
  imp: GedcomImport;
  active: boolean;
  onOpen: () => void;
}) {
  const { t } = useTranslation();
  const formatDate = useFormatDate();
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 py-2">
      <div>
        <span className="font-medium">{imp.filename}</span>{" "}
        <Badge tone={TONE[imp.status]}>{t(`imports.status.${imp.status}`)}</Badge>
        <div className="text-bark-700 text-xs">
          {formatDate(imp.created_at)}
          {imp.created_by && ` · ${imp.created_by}`}
          {imp.preview && ` · ${t("imports.people", { count: imp.preview.counts.persons })}`}
        </div>
      </div>
      {!active && (
        <Button variant="ghost" onClick={onOpen}>
          {t("imports.open")}
        </Button>
      )}
    </li>
  );
}

function ImportDetail({
  treeId,
  imp,
  newTree,
}: {
  treeId: string;
  imp: GedcomImport;
  /** The tree was created just for this file (from "Import GEDCOM" on the tree list). */
  newTree: boolean;
}) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const navigate = useNavigate();
  const action = useImportAction(treeId);
  const removeTree = useDeleteTreeById();
  const cancel = () =>
    action.mutate(
      { id: imp.id, action: "cancel" },
      {
        onSuccess: () =>
          newTree &&
          removeTree.mutate(treeId, { onSuccess: () => void navigate("/", { replace: true }) }),
      },
    );
  // When the worker finishes importing or undoing, the tree's people have changed.
  const last = useRef(imp.status);
  useEffect(() => {
    if (last.current !== imp.status && !BUSY.includes(imp.status)) {
      void qc.invalidateQueries({ queryKey: ["tree", treeId] });
    }
    last.current = imp.status;
  }, [imp.status, qc, treeId]);

  return (
    <Card className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2" aria-live="polite">
        <h2 className="font-semibold">{imp.filename}</h2>
        <Badge tone={TONE[imp.status]}>{t(`imports.status.${imp.status}`)}</Badge>
      </div>
      {BUSY.includes(imp.status) && (
        <p className="text-bark-700 flex items-center gap-2 text-sm">
          <Spinner /> {t(`imports.busy.${imp.status}`)}
        </p>
      )}
      {newTree && (imp.status === "ready" || imp.status === "analyzing") && (
        <p className="text-bark-700 text-xs">{t("imports.newTreeHint")}</p>
      )}
      {imp.status === "failed" && (
        <Alert>
          {t(`imports.errors.${imp.error ?? "import_failed"}`, t("imports.errors.import_failed"))}
        </Alert>
      )}
      <ErrorAlert error={action.error} />
      {imp.status === "ready" && imp.preview && (
        <Preview
          imp={imp}
          busy={action.isPending}
          onImport={(merge) => action.mutate({ id: imp.id, action: "confirm", merge })}
          onCancel={cancel}
        />
      )}
      {(imp.status === "done" || imp.status === "undone") && imp.result && (
        <Result
          treeId={treeId}
          imp={imp}
          busy={action.isPending}
          onUndo={() =>
            window.confirm(t("imports.undoConfirm")) &&
            action.mutate({ id: imp.id, action: "undo" })
          }
        />
      )}
    </Card>
  );
}

const COUNT_KEYS: (keyof ImportCounts)[] = [
  "persons",
  "families",
  "events",
  "places",
  "sources",
  "citations",
];

function Preview({
  imp,
  busy,
  onImport,
  onCancel,
}: {
  imp: GedcomImport;
  busy: boolean;
  onImport: (merge: Record<string, string>) => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  const p = imp.preview!;
  // Strong matches (same names, same birth year) are pre-selected as "the same person".
  const [merge, setMerge] = useState<Record<string, string>>(() =>
    Object.fromEntries(p.duplicates.filter((d) => d.strong).map((d) => [d.xref, d.existing.id])),
  );
  const [showPeople, setShowPeople] = useState(false);
  const creating = p.counts.persons - Object.keys(merge).length;

  return (
    <div className="space-y-4">
      <dl className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {COUNT_KEYS.map((k) => (
          <div key={k} className="bg-bark-50 rounded-md p-3">
            <dt className="text-bark-700 text-xs">{t(`imports.counts.${k}`)}</dt>
            <dd className="font-serif text-2xl font-semibold">{p.counts[k]}</dd>
          </div>
        ))}
      </dl>
      <p className="text-bark-700 text-xs">
        {[
          p.header.source && t("imports.from", { source: p.header.source }),
          p.header.version && `GEDCOM ${p.header.version}`,
          p.encoding,
        ]
          .filter(Boolean)
          .join(" · ")}
      </p>

      {(p.warnings.length > 0 || p.skipped_tags.length > 0) && (
        <Alert kind="info">
          <ul className="list-disc space-y-1 pl-5">
            {p.warnings.map((w) => (
              <li key={w.code}>{t(`imports.warnings.${w.code}`, { count: w.count })}</li>
            ))}
            {p.skipped_tags.length > 0 && (
              <li>
                {t("imports.warnings.skipped_tags")}{" "}
                <span className="font-mono text-xs">
                  {p.skipped_tags.map((s) => `${s.tag} ×${s.count}`).join(", ")}
                </span>
              </li>
            )}
          </ul>
        </Alert>
      )}

      {p.duplicates.length > 0 && (
        <section className="space-y-2">
          <h3 className="font-semibold">{t("imports.duplicates.title")}</h3>
          <p className="text-bark-700 text-sm">{t("imports.duplicates.hint")}</p>
          <ul className="divide-bark-100 border-bark-100 divide-y rounded-md border text-sm">
            {p.duplicates.map((d) => (
              <li key={d.xref} className="flex flex-wrap items-center justify-between gap-3 p-3">
                <div>
                  <div>
                    <span className="font-medium">{d.name}</span>{" "}
                    <span className="text-bark-700">{d.years}</span>
                  </div>
                  <div className="text-bark-700 text-xs">
                    {t("imports.duplicates.inTree", {
                      name: d.existing.name,
                      years: d.existing.years || "—",
                    })}
                    {!d.strong && ` · ${t("imports.duplicates.possible")}`}
                  </div>
                </div>
                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    className="border-bark-100 size-4 rounded"
                    checked={d.xref in merge}
                    onChange={(e) =>
                      setMerge((m) => {
                        const next = { ...m };
                        if (e.target.checked) next[d.xref] = d.existing.id;
                        else delete next[d.xref];
                        return next;
                      })
                    }
                  />
                  {t("imports.duplicates.same")}
                </label>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section>
        <button
          type="button"
          className="text-leaf-700 text-sm underline"
          aria-expanded={showPeople}
          onClick={() => setShowPeople((v) => !v)}
        >
          {showPeople ? t("imports.hidePeople") : t("imports.showPeople")}
        </button>
        {showPeople && (
          <ul className="mt-2 max-h-80 columns-1 overflow-y-auto text-sm sm:columns-2">
            {p.people.map((person) => (
              <li key={person.xref} className="break-inside-avoid py-0.5">
                {person.name} <span className="text-bark-700 text-xs">{person.years}</span>
              </li>
            ))}
            {p.counts.persons > p.people.length && (
              <li className="text-bark-700 text-xs">
                {t("imports.morePeople", { count: p.counts.persons - p.people.length })}
              </li>
            )}
          </ul>
        )}
      </section>

      <div className="flex flex-wrap justify-end gap-2">
        <Button variant="secondary" disabled={busy} onClick={onCancel}>
          {t("common.cancel")}
        </Button>
        <Button busy={busy} onClick={() => onImport(merge)}>
          {t("imports.import", { count: creating })}
        </Button>
      </div>
    </div>
  );
}

function warningText(t: TFunction, w: ImportWarning): string {
  const reason = w.reason ? t(`errors.${w.reason}`, { defaultValue: t("errors.generic") }) : "";
  const type = w.type ? t(`eventTypes.${w.type}`, { defaultValue: w.type }) : "";
  return t(`imports.result.${w.code}`, { ...w, reason, type });
}

function Result({
  treeId,
  imp,
  busy,
  onUndo,
}: {
  treeId: string;
  imp: GedcomImport;
  busy: boolean;
  onUndo: () => void;
}) {
  const { t } = useTranslation();
  const r = imp.result!;
  const c = r.counts;
  const lines = [
    ["persons_created", c.persons_created],
    ["persons_merged", c.persons_merged],
    ["partnerships", c.partnerships],
    ["parent_links", c.parent_links],
    ["events", c.events],
    ["places_created", c.places_created],
    ["sources", c.sources],
    ["citations", c.citations],
  ].filter(([, n]) => n) as [string, number][];

  return (
    <div className="space-y-3">
      {imp.status === "done" ? (
        <Alert kind="success">{t("imports.done")}</Alert>
      ) : (
        <Alert kind="info">{t("imports.undone")}</Alert>
      )}
      <ul className="text-sm">
        {lines.map(([key, n]) => (
          <li key={key}>{t(`imports.result.counts.${key}`, { count: n })}</li>
        ))}
      </ul>
      {r.warnings.length > 0 && (
        <details className="text-sm">
          <summary className="cursor-pointer">
            {t("imports.result.warnings", { count: c.warnings ?? r.warnings.length })}
          </summary>
          <ul className="text-bark-700 mt-2 list-disc space-y-1 pl-5">
            {r.warnings.map((w, i) => (
              <li key={i}>{warningText(t, w)}</li>
            ))}
          </ul>
        </details>
      )}
      {imp.status === "done" && (
        <div className="flex flex-wrap justify-end gap-2">
          <Button variant="ghost" className="text-red-700" busy={busy} onClick={onUndo}>
            {t("imports.undo")}
          </Button>
          <Link
            to={`/trees/${treeId}`}
            className="bg-leaf-700 hover:bg-leaf-600 text-on-leaf inline-flex items-center rounded-md px-3 py-1.5 text-sm"
          >
            {t("imports.openTree")}
          </Link>
        </div>
      )}
    </div>
  );
}
