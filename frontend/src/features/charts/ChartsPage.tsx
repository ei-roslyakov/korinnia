import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";

import { Button, ErrorAlert, PageHeader, Select, Spinner } from "@/components/ui";
import { useTree } from "@/features/tree/api";
import { exportFileName, type ExportFormat } from "@/features/tree/canvas/exportTree";
import type { PersonSummary } from "@/lib/genealogy";
import { useToast } from "@/lib/toast";

import { useLineage } from "./api";
import { DescendancyList } from "./DescendancyList";
import { exportChart } from "./exportChart";
import { FanChart } from "./FanChart";
import { descendancy, pedigreeSlots } from "./lineage";
import { PanZoom } from "./PanZoom";
import { PedigreeChart } from "./PedigreeChart";

const CHART_KINDS = ["fan", "pedigree", "descendants"] as const;
type ChartKind = (typeof CHART_KINDS)[number];

const GENERATIONS: Record<Exclude<ChartKind, "descendants">, [number, number, number]> = {
  // [min, max, default], the person included
  fan: [4, 8, 6],
  pedigree: [4, 6, 4],
};
const DESCENDANT_DEPTH = 8;

/** A person's ancestors as a fan or a pedigree, or their descendants as a numbered outline
 * (D118). The URL is shareable: /trees/:id/charts/fan/:personId?gen=6 */
export function ChartsPage() {
  const { t } = useTranslation();
  const { treeId = "", kind: rawKind = "fan", personId = "" } = useParams();
  const kind: ChartKind = CHART_KINDS.includes(rawKind as ChartKind)
    ? (rawKind as ChartKind)
    : "fan";
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const toast = useToast();
  const tree = useTree(treeId);
  const range = kind === "descendants" ? null : GENERATIONS[kind];
  const generations = range
    ? Math.min(range[1], Math.max(range[0], Number(params.get("gen")) || range[2]))
    : 0;
  const half = params.get("full") !== "1";
  const namesOnly = params.get("names") === "1";
  const data = useLineage(
    treeId,
    personId,
    kind === "descendants" ? "descendants" : "ancestors",
    range ? generations - 1 : DESCENDANT_DEPTH,
  );
  const chart = useRef<SVGSVGElement | HTMLDivElement | null>(null);
  const [exporting, setExporting] = useState<ExportFormat | null>(null);

  const set = (k: string, v: string | null) => {
    const next = new URLSearchParams(params);
    if (v) next.set(k, v);
    else next.delete(k);
    setParams(next, { replace: true });
  };
  const chartUrl = (k: ChartKind, id = personId) =>
    `/trees/${treeId}/charts/${k}/${id}${k === kind && params.size ? `?${params.toString()}` : ""}`;
  const open = (p: PersonSummary) => void navigate(chartUrl(kind, p.id));
  const personLink = (id: string) => `/trees/${treeId}/people/${id}`;

  const root = data.data?.persons.find((p) => p.id === data.data?.root_id);
  const title = root ? t(`charts.${kind}.of`, { name: root.display_name }) : "";

  const download = async (format: ExportFormat) => {
    if (!chart.current || !root) return;
    setExporting(format);
    try {
      await exportChart({
        element: chart.current,
        format,
        title,
        subtitle: [tree.data?.name, new Date().toLocaleDateString()].filter(Boolean).join(" · "),
        fileName: exportFileName(`${root.display_name}-${t(`charts.${kind}.file`)}`),
      });
    } catch {
      toast(t("canvas.export.failed"), "error");
    } finally {
      setExporting(null);
    }
  };

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <div className="flex flex-wrap gap-4 text-sm print:hidden">
        <Link to={`/trees/${treeId}?person=${personId}`} className="text-leaf-700 underline">
          ← {t("person.backToTree")}
        </Link>
        {root && (
          <Link to={personLink(personId)} className="text-leaf-700 underline">
            {root.display_name}
          </Link>
        )}
      </div>
      <PageHeader title={title || t("charts.title")} />
      <nav className="flex flex-wrap gap-1" aria-label={t("charts.title")}>
        {CHART_KINDS.map((k) => (
          <Link
            key={k}
            to={chartUrl(k)}
            aria-current={k === kind ? "page" : undefined}
            className={`rounded-full border px-3 py-1 text-sm ${k === kind ? "bg-leaf-700 text-on-leaf border-transparent" : "border-bark-100 bg-surface"}`}
          >
            {t(`charts.${k}.title`)}
          </Link>
        ))}
      </nav>
      <div className="flex flex-wrap items-center gap-3 text-sm">
        {range && (
          <label className="flex items-center gap-1.5">
            {t("charts.generations")}
            <Select
              className="w-auto"
              value={generations}
              onChange={(e) => set("gen", e.target.value)}
            >
              {Array.from({ length: range[1] - range[0] + 1 }, (_, i) => range[0] + i).map((g) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </Select>
          </label>
        )}
        {kind === "fan" && (
          <label className="flex items-center gap-1.5">
            <input
              type="checkbox"
              checked={!half}
              onChange={(e) => set("full", e.target.checked ? "1" : null)}
            />
            {t("charts.fan.full")}
          </label>
        )}
        {kind === "descendants" && (
          <label className="flex items-center gap-1.5">
            <input
              type="checkbox"
              checked={namesOnly}
              onChange={(e) => set("names", e.target.checked ? "1" : null)}
            />
            {t("charts.descendants.namesOnly")}
          </label>
        )}
        <span className="flex-1" />
        <Button
          variant="secondary"
          busy={exporting === "png"}
          disabled={!root}
          onClick={() => void download("png")}
        >
          {t("charts.download", { format: "PNG" })}
        </Button>
        <Button
          variant="secondary"
          busy={exporting === "pdf"}
          disabled={!root}
          onClick={() => void download("pdf")}
        >
          {t("charts.download", { format: "PDF" })}
        </Button>
      </div>
      {kind !== "descendants" && (
        <p className="text-bark-700 text-xs">
          <span
            className="mr-1 inline-block size-3 rounded-sm align-middle"
            style={{ background: "var(--k-sky-100)" }}
          />
          {t("charts.paternal")}{" "}
          <span
            className="mr-1 ml-3 inline-block size-3 rounded-sm align-middle"
            style={{ background: "var(--k-rose-100)" }}
          />
          {t("charts.maternal")} · {t("charts.legend")}
        </p>
      )}
      {data.isPending && <Spinner />}
      <ErrorAlert error={data.error} />
      {data.data && kind === "fan" && (
        <PanZoom label={title}>
          <FanChart
            ref={(el) => {
              chart.current = el;
            }}
            slots={pedigreeSlots(data.data, generations)}
            generations={generations}
            half={half}
            onOpen={open}
          />
        </PanZoom>
      )}
      {data.data && kind === "pedigree" && (
        <PanZoom label={title}>
          <PedigreeChart
            ref={(el) => {
              chart.current = el;
            }}
            slots={pedigreeSlots(data.data, generations)}
            generations={generations}
            onOpen={open}
          />
        </PanZoom>
      )}
      {data.data && kind === "descendants" && (
        <DescendantsView
          tree={descendancy(data.data)}
          truncated={data.data.truncated}
          personLink={personLink}
          namesOnly={namesOnly}
          setRef={(el) => {
            chart.current = el;
          }}
        />
      )}
      {data.data?.truncated && kind !== "descendants" && (
        <p className="text-bark-700 text-xs">{t("charts.more")}</p>
      )}
    </div>
  );
}

function DescendantsView({
  tree,
  truncated,
  personLink,
  namesOnly,
  setRef,
}: {
  tree: ReturnType<typeof descendancy>;
  truncated: boolean;
  personLink: (id: string) => string;
  namesOnly: boolean;
  setRef: (el: HTMLDivElement | null) => void;
}) {
  const { t } = useTranslation();
  if (!tree) return null;
  return (
    <div className="border-bark-100 rounded-lg border">
      <DescendancyList ref={setRef} root={tree} personLink={personLink} namesOnly={namesOnly} />
      {truncated && (
        <p className="text-bark-700 px-3 pb-2 text-xs">
          {t("charts.descendants.more", { count: DESCENDANT_DEPTH })}
        </p>
      )}
    </div>
  );
}
