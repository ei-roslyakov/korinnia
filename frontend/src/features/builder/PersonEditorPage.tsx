import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";

import { Alert, Button, ErrorAlert, PageHeader, Spinner } from "@/components/ui";
import { usePerson } from "@/features/person/api";
import { MediaTab } from "@/features/media/MediaTab";
import { SourcesTab } from "@/features/sources/SourcesTab";
import { useTree } from "@/features/tree/api";
import type { PersonDetail } from "@/lib/genealogy";
import { atLeast } from "@/lib/types";

import { DeletePersonDialog } from "./DeletePersonDialog";
import { EventsTab } from "./EventsTab";
import { FamilyTab } from "./FamilyTab";
import { HistoryTab } from "./HistoryTab";
import { PersonForm } from "./PersonForm";

const TABS = ["details", "media", "events", "family", "sources", "history"] as const;
type Tab = (typeof TABS)[number];

export function PersonEditorPage() {
  const { t } = useTranslation();
  const { treeId = "", personId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const tree = useTree(treeId);
  const person = usePerson(treeId, personId);
  const [deleting, setDeleting] = useState(false);
  const [saved, setSaved] = useState<PersonDetail | null>(null);
  const tab = (TABS as readonly string[]).includes(params.get("tab") ?? "")
    ? (params.get("tab") as Tab)
    : "details";

  if (tree.isPending || person.isPending) return <Spinner />;
  if (tree.error || person.error) return <ErrorAlert error={tree.error ?? person.error} />;
  if (!atLeast(tree.data.my_role, "editor")) return <Alert>{t("errors.permission_denied")}</Alert>;
  const p = person.data;

  return (
    <div className="mx-auto max-w-4xl">
      <Link
        to={`/trees/${treeId}?mode=edit&person=${personId}`}
        className="text-leaf-700 text-sm underline"
      >
        ← {t("person.backToTree")}
      </Link>
      <PageHeader
        title={p.display_name}
        actions={
          <>
            <Link
              to={`/trees/${treeId}/people/${personId}`}
              className="border-bark-100 hover:bg-bark-50 bg-surface inline-flex items-center rounded-md border px-3 py-1.5 text-sm"
            >
              {t("builder.viewPage")}
            </Link>
            <Button variant="danger" onClick={() => setDeleting(true)}>
              {t("common.delete")}
            </Button>
          </>
        }
      />
      <nav className="border-bark-100 mb-6 flex gap-1 overflow-x-auto border-b" role="tablist">
        {TABS.map((x) => (
          <button
            key={x}
            type="button"
            role="tab"
            aria-selected={tab === x}
            className={`-mb-px shrink-0 border-b-2 px-3 py-2 text-sm whitespace-nowrap ${tab === x ? "border-leaf-700 text-leaf-700 font-semibold" : "text-bark-700 border-transparent"}`}
            onClick={() => setParams({ tab: x }, { replace: true })}
          >
            {t(`builder.tabs.${x}`)}
          </button>
        ))}
      </nav>
      {saved && tab === "details" && (
        <div className="mb-4 space-y-2">
          <Alert kind="success">{t("common.saved")}</Alert>
          {saved.warnings.length > 0 && (
            <Alert kind="info">
              {saved.warnings.map((w, i) => (
                <div key={i}>{t(`warnings.${w.code}`, { ...w.params, defaultValue: w.code })}</div>
              ))}
            </Alert>
          )}
        </div>
      )}
      {tab === "details" && (
        // Remount on external changes (e.g. a restored revision) to show fresh data.
        <PersonForm key={p.updated_at} treeId={treeId} person={p} onSaved={setSaved} />
      )}
      {tab === "media" && (
        <MediaTab treeId={treeId} person={p} onChanged={() => void person.refetch()} />
      )}
      {tab === "events" && <EventsTab treeId={treeId} person={p} />}
      {tab === "family" && <FamilyTab treeId={treeId} person={p} />}
      {tab === "sources" && <SourcesTab treeId={treeId} person={p} />}
      {tab === "history" && <HistoryTab treeId={treeId} personId={personId} />}
      {deleting && (
        <DeletePersonDialog
          treeId={treeId}
          personId={personId}
          onClose={() => setDeleting(false)}
          onDeleted={() => void navigate(`/trees/${treeId}?mode=edit`, { replace: true })}
        />
      )}
    </div>
  );
}
