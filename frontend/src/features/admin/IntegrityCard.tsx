import { useTranslation } from "react-i18next";

import { Alert, Badge, Button, Card, ErrorAlert, Spinner } from "@/components/ui";
import { useFormatBytes, useFormatDate } from "@/lib/hooks";

import { useIntegrity, useStartIntegrityCheck } from "./api";

/** Integrity of stored originals: the last checks, their problems, "check now". */
export function IntegrityCard() {
  const { t } = useTranslation();
  const formatDate = useFormatDate();
  const formatBytes = useFormatBytes();
  const integrity = useIntegrity();
  const start = useStartIntegrityCheck();
  const data = integrity.data;
  const last = data?.runs[0];
  const running = last?.status === "running";
  const lastDone = data?.runs.find((r) => r.finished_at);

  return (
    <Card className="max-w-3xl space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold">{t("integrity.title")}</h2>
        <Button
          variant="secondary"
          busy={start.isPending}
          disabled={running}
          onClick={() => start.mutate()}
        >
          {t("integrity.checkNow")}
        </Button>
      </div>
      <p className="text-bark-700 text-sm">{t("integrity.hint")}</p>
      {integrity.isPending && <Spinner />}
      <ErrorAlert error={integrity.error ?? start.error} />
      {data && (
        <p className="text-sm">
          {t("integrity.stored", {
            count: data.total_files,
            size: formatBytes(data.total_bytes),
          })}
        </p>
      )}
      {running && last && (
        <p className="text-bark-700 flex items-center gap-2 text-sm" aria-live="polite">
          <Spinner />
          {t("integrity.running", { done: last.files_checked, total: data?.total_files ?? 0 })}
        </p>
      )}
      {lastDone && (
        <div className="space-y-2 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            <span>
              {t("integrity.lastCheck", { date: formatDate(lastDone.finished_at) })}
              {" · "}
              {t(`integrity.trigger.${lastDone.trigger}`, { name: lastDone.triggered_by ?? "" })}
            </span>
            {lastDone.status === "failed" ? (
              <Badge tone="red">{t("integrity.failed")}</Badge>
            ) : lastDone.problems ? (
              <Badge tone="red">{t("integrity.problems", { count: lastDone.problems })}</Badge>
            ) : (
              <Badge tone="green">{t("integrity.allGood")}</Badge>
            )}
          </div>
          {lastDone.status !== "failed" && (
            <p className="text-bark-700 text-xs">
              {t("integrity.checked", {
                count: lastDone.files_checked,
                size: formatBytes(lastDone.bytes_checked),
              })}
              {lastDone.untracked_files > 0 &&
                ` · ${t("integrity.untracked", { count: lastDone.untracked_files })}`}
            </p>
          )}
        </div>
      )}
      {data && !lastDone && !running && (
        <p className="text-bark-700 text-sm">{t("integrity.never")}</p>
      )}
      {data && data.issues.length > 0 && (
        <>
          <Alert>{t("integrity.issuesHint")}</Alert>
          <div className="border-bark-100 overflow-x-auto rounded-md border">
            <table className="w-full text-left text-sm">
              <thead className="border-bark-100 bg-bark-50 text-bark-700 border-b">
                <tr>
                  <th className="px-3 py-2">{t("integrity.file")}</th>
                  <th className="px-3 py-2">{t("integrity.tree")}</th>
                  <th className="px-3 py-2">{t("integrity.problem")}</th>
                </tr>
              </thead>
              <tbody className="divide-bark-100 divide-y">
                {data.issues.map((i) => (
                  <tr key={i.key}>
                    <td className="px-3 py-2">
                      <div>{i.filename ?? "—"}</div>
                      <div className="text-bark-700 font-mono text-xs break-all">{i.key}</div>
                    </td>
                    <td className="px-3 py-2">{i.tree_name ?? "—"}</td>
                    <td className="px-3 py-2">
                      <Badge tone="red">{t(`integrity.kinds.${i.problem}`)}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </Card>
  );
}
