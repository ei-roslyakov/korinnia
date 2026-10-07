import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router";

import { ErrorAlert, Input, PageHeader, Select, Spinner } from "@/components/ui";
import { useFormatDate } from "@/lib/hooks";
import { useMe } from "@/features/auth/api";
import type { AuditEntry } from "@/lib/types";

import { useAuditActions, useAuditLog, type AuditFilters } from "./api";
import { Pager } from "./UsersPage";

/** Audit log viewer. Under /trees/:treeId/audit it shows only that tree's entries. */
export function AuditLogPage() {
  const { t } = useTranslation();
  const { treeId } = useParams();
  const me = useMe();
  const [filters, setFilters] = useState<AuditFilters>({});
  const log = useAuditLog(treeId, filters);
  const actions = useAuditActions(Boolean(me.data?.is_superadmin));
  const set = (patch: Partial<AuditFilters>) => setFilters((f) => ({ ...f, ...patch, offset: 0 }));

  return (
    <div>
      <PageHeader
        title={t("audit.title")}
        actions={
          treeId && (
            <Link to={`/trees/${treeId}`} className="text-leaf-700 text-sm underline">
              {t("common.back")}
            </Link>
          )
        }
      />
      <div className="mb-4 grid gap-3 sm:grid-cols-4">
        {actions.data ? (
          <Select
            aria-label={t("audit.action")}
            value={filters.action ?? ""}
            onChange={(e) => set({ action: e.target.value || undefined })}
          >
            <option value="">{t("audit.allActions")}</option>
            {actions.data.map((a) => (
              <option key={a} value={a}>
                {a}
              </option>
            ))}
          </Select>
        ) : (
          <Input
            aria-label={t("audit.action")}
            placeholder={t("audit.action")}
            value={filters.action ?? ""}
            onChange={(e) => set({ action: e.target.value || undefined })}
          />
        )}
        <Select
          aria-label={t("audit.entity")}
          value={filters.entity_type ?? ""}
          onChange={(e) => set({ entity_type: e.target.value || undefined })}
        >
          <option value="">{t("audit.allEntities")}</option>
          {["user", "tree", "membership", "invitation"].map((x) => (
            <option key={x} value={x}>
              {x}
            </option>
          ))}
        </Select>
        <Input
          type="date"
          aria-label={t("audit.from")}
          value={filters.date_from?.slice(0, 10) ?? ""}
          onChange={(e) =>
            set({ date_from: e.target.value ? `${e.target.value}T00:00:00` : undefined })
          }
        />
        <Input
          type="date"
          aria-label={t("audit.to")}
          value={filters.date_to?.slice(0, 10) ?? ""}
          onChange={(e) =>
            set({ date_to: e.target.value ? `${e.target.value}T23:59:59` : undefined })
          }
        />
      </div>
      {log.isPending && <Spinner />}
      <ErrorAlert error={log.error} />
      {log.data && (
        <>
          {log.data.items.length === 0 && (
            <p className="text-bark-700 text-sm">{t("audit.empty")}</p>
          )}
          <ul className="space-y-2">
            {log.data.items.map((entry) => (
              <AuditRow key={entry.id} entry={entry} />
            ))}
          </ul>
          <Pager
            total={log.data.total}
            offset={filters.offset ?? 0}
            limit={50}
            onChange={(offset) => setFilters((f) => ({ ...f, offset }))}
          />
        </>
      )}
    </div>
  );
}

function AuditRow({ entry }: { entry: AuditEntry }) {
  const { t } = useTranslation();
  const formatDate = useFormatDate();
  const hasDetails = entry.before !== null || entry.after !== null;
  return (
    <li className="border-bark-100 rounded-md border bg-white px-3 py-2 text-sm">
      <details>
        <summary
          className={`flex flex-wrap gap-x-3 ${hasDetails ? "cursor-pointer" : "list-none"}`}
        >
          <span className="text-bark-700">{formatDate(entry.created_at)}</span>
          <span className="font-mono">{entry.action}</span>
          <span>{entry.user_label ?? t("audit.system")}</span>
          {entry.ip_address && <span className="text-bark-700">{entry.ip_address}</span>}
        </summary>
        {hasDetails && (
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            <pre className="overflow-x-auto rounded bg-red-50 p-2 text-xs">
              {t("audit.before")}: {JSON.stringify(entry.before, null, 2)}
            </pre>
            <pre className="overflow-x-auto rounded bg-green-50 p-2 text-xs">
              {t("audit.after")}: {JSON.stringify(entry.after, null, 2)}
            </pre>
          </div>
        )}
      </details>
    </li>
  );
}
