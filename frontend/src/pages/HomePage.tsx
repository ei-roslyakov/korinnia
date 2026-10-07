import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { getMeta, getReadiness, type CheckStatus } from "@/lib/api";

function StatusBadge({ status }: { status: CheckStatus | "loading" }) {
  const { t } = useTranslation();
  const styles = {
    ok: "bg-green-100 text-green-800",
    error: "bg-red-100 text-red-800",
    loading: "bg-bark-100 text-bark-700",
  } as const;
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${styles[status]}`}>
      {t(`status.${status}`)}
    </span>
  );
}

export function HomePage() {
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

  return (
    <div className="space-y-8">
      <section>
        <h1 className="font-serif text-3xl font-semibold">{t("app.name")}</h1>
        <p className="text-bark-700 mt-2">{t("app.tagline")}</p>
        <p className="text-bark-700 mt-4">{t("home.comingSoon")}</p>
      </section>

      <section className="border-bark-100 max-w-md rounded-lg border bg-white p-4 shadow-sm">
        <h2 className="mb-3 font-semibold">{t("status.title")}</h2>
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
              <StatusBadge status={status} />
            </li>
          ))}
        </ul>
        {meta.data && (
          <p className="text-bark-700 mt-3 text-xs">
            {t("status.version", { version: meta.data.version })}
          </p>
        )}
      </section>
    </div>
  );
}
