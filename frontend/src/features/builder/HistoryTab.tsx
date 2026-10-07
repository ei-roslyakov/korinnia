import { useTranslation } from "react-i18next";

import { Button, ErrorAlert, Spinner } from "@/components/ui";
import { useFormatDate } from "@/lib/hooks";
import type { AuditEntry } from "@/lib/types";

import { usePersonHistory, useRestoreRevision } from "./api";

function changedKeys(entry: AuditEntry): string[] {
  const before = entry.before ?? {};
  const after = entry.after ?? {};
  return [...new Set([...Object.keys(before), ...Object.keys(after)])].filter(
    (k) => JSON.stringify(before[k]) !== JSON.stringify(after[k]),
  );
}

/** All revisions of a person, newest first; any version can be restored. */
export function HistoryTab({ treeId, personId }: { treeId: string; personId: string }) {
  const { t } = useTranslation();
  const formatDate = useFormatDate();
  const history = usePersonHistory(treeId, personId);
  const restore = useRestoreRevision(treeId);

  if (history.isPending) return <Spinner />;
  if (history.error) return <ErrorAlert error={history.error} />;

  return (
    <div className="space-y-3">
      <p className="text-bark-700 text-sm">{t("builder.history.hint")}</p>
      <ErrorAlert error={restore.error} />
      <ol className="space-y-2">
        {history.data.items.map((entry, i) => {
          const keys = entry.before ? changedKeys(entry) : [];
          return (
            <li
              key={entry.id}
              className="border-bark-100 rounded-md border bg-white px-3 py-2 text-sm"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <span className="font-medium">
                    {t(`builder.history.actions.${entry.action.split(".")[1]}`, {
                      defaultValue: entry.action,
                    })}
                  </span>
                  <span className="text-bark-700">
                    {" "}
                    · {formatDate(entry.created_at)} · {entry.user_label ?? t("audit.system")}
                  </span>
                </div>
                {entry.after && i > 0 && (
                  <Button
                    variant="secondary"
                    busy={restore.isPending && restore.variables === entry.id}
                    onClick={() =>
                      window.confirm(t("builder.history.confirm")) && restore.mutate(entry.id)
                    }
                  >
                    {t("builder.history.restore")}
                  </Button>
                )}
              </div>
              {keys.length > 0 && (
                <div className="text-bark-700 mt-1 text-xs">
                  {t("builder.history.changed")}:{" "}
                  {keys
                    .map((k) => t(`builder.history.fields.${k}`, { defaultValue: k }))
                    .join(", ")}
                </div>
              )}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
