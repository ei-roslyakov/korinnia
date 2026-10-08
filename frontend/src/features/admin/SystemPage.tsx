import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { Badge, Card, PageHeader } from "@/components/ui";
import { getMeta, getReadiness, type CheckStatus } from "@/lib/api";

import { IntegrityCard } from "./IntegrityCard";

export function SystemPage() {
  const { t } = useTranslation();
  const meta = useQuery({ queryKey: ["meta"], queryFn: getMeta });
  const ready = useQuery({ queryKey: ["readyz"], queryFn: getReadiness, refetchInterval: 30_000 });

  const apiStatus: CheckStatus | "loading" = meta.isPending
    ? "loading"
    : meta.isError
      ? "error"
      : "ok";
  const checkStatus = (name: string): CheckStatus | "loading" =>
    ready.isPending ? "loading" : ready.isError ? "error" : (ready.data.checks[name] ?? "error");
  const tone = { ok: "green", error: "red", loading: "neutral" } as const;

  return (
    <div className="space-y-4">
      <PageHeader title={t("status.title")} />
      <Card className="max-w-md">
        <ul className="space-y-2 text-sm">
          {(
            [
              ["api", apiStatus],
              ["database", checkStatus("database")],
              ["storage", checkStatus("storage")],
            ] as const
          ).map(([key, status]) => (
            <li key={key} className="flex items-center justify-between">
              <span>{t(`status.${key}`)}</span>
              <Badge tone={tone[status]}>{t(`status.${status}`)}</Badge>
            </li>
          ))}
        </ul>
        {meta.data && (
          <p className="text-bark-700 mt-3 text-xs">
            {t("status.version", { version: meta.data.version })}
          </p>
        )}
      </Card>
      <IntegrityCard />
    </div>
  );
}
