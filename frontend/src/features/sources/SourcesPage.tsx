import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router";

import { Badge, Button, Card, ErrorAlert, Input, PageHeader, Spinner } from "@/components/ui";
import { CitationList } from "@/features/collab/CitationList";
import { useDeleteSource, useSourceCitations, useSources } from "@/features/collab/api";
import { useTree } from "@/features/tree/api";
import type { Source } from "@/lib/genealogy";
import { atLeast } from "@/lib/types";

import { SourceDialog } from "./SourceDialog";

export function SourcesPage() {
  const { t } = useTranslation();
  const { treeId = "" } = useParams();
  const tree = useTree(treeId);
  const [q, setQ] = useState("");
  const sources = useSources(treeId, q);
  const del = useDeleteSource(treeId);
  const [editing, setEditing] = useState<Source | "new" | null>(null);
  const [open, setOpen] = useState<string | null>(null);
  const canEdit = tree.data ? atLeast(tree.data.my_role, "editor") : false;

  return (
    <div className="mx-auto max-w-4xl">
      <Link to={`/trees/${treeId}`} className="text-leaf-700 text-sm underline">
        ← {t("person.backToTree")}
      </Link>
      <PageHeader
        title={t("collab.sources")}
        actions={
          canEdit && (
            <Button onClick={() => setEditing("new")}>+ {t("collab.sourcesPage.new")}</Button>
          )
        }
      />
      <p className="text-bark-700 mb-4 text-sm">{t("collab.sourcesPage.hint")}</p>
      <Input
        type="search"
        className="mb-4 max-w-sm"
        aria-label={t("collab.sourcesPage.search")}
        placeholder={t("collab.sourcesPage.search")}
        value={q}
        onChange={(e) => setQ(e.target.value)}
      />
      {sources.isPending && <Spinner />}
      <ErrorAlert error={sources.error ?? del.error} />
      {sources.data?.items.length === 0 && (
        <p className="text-bark-700 text-sm">{t("collab.sourcesPage.none")}</p>
      )}
      <ul className="space-y-2">
        {sources.data?.items.map((s) => (
          <li key={s.id}>
            <Card className="space-y-2">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <div className="font-medium">{s.title}</div>
                  <div className="text-bark-700 text-sm">
                    {[
                      t(`collab.sourceTypes.${s.type}`),
                      s.archive_name,
                      s.reference_number,
                      s.author,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </div>
                  {s.url && (
                    <a
                      href={s.url}
                      target="_blank"
                      rel="noopener noreferrer nofollow"
                      className="text-leaf-700 text-sm underline"
                    >
                      {s.url}
                    </a>
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-1">
                  <Button variant="ghost" onClick={() => setOpen(open === s.id ? null : s.id)}>
                    <Badge>{t("collab.sourcesPage.citations", { count: s.citation_count })}</Badge>
                  </Button>
                  {canEdit && (
                    <>
                      <Button variant="secondary" onClick={() => setEditing(s)}>
                        {t("builder.edit")}
                      </Button>
                      <Button
                        variant="ghost"
                        className="text-red-700"
                        onClick={() =>
                          window.confirm(t("collab.sourcesPage.confirmDelete")) && del.mutate(s.id)
                        }
                      >
                        {t("common.delete")}
                      </Button>
                    </>
                  )}
                </div>
              </div>
              {s.notes && <p className="text-sm whitespace-pre-line">{s.notes}</p>}
              {open === s.id && <SourceCitations treeId={treeId} sourceId={s.id} />}
            </Card>
          </li>
        ))}
      </ul>
      {editing && (
        <SourceDialog
          treeId={treeId}
          source={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}

function SourceCitations({ treeId, sourceId }: { treeId: string; sourceId: string }) {
  const citations = useSourceCitations(treeId, sourceId);
  if (citations.isPending) return <Spinner />;
  return <CitationList citations={citations.data ?? []} />;
}
