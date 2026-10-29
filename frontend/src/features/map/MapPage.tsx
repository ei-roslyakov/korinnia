import "leaflet/dist/leaflet.css";

import L from "leaflet";
import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useParams, useSearchParams } from "react-router";

import { Card, ErrorAlert, PageHeader, Spinner } from "@/components/ui";
import { useMapData } from "@/features/insights/api";
import { CategoryFilter, FactLine } from "@/features/insights/FactLine";
import { CATEGORY_STYLE, parseCategories } from "@/features/insights/facts";
import { PersonFilter } from "@/features/insights/PersonFilter";
import { PlaceLink } from "@/features/places/PlaceLink";
import { factCategory, type FactCategory, type MapPoint } from "@/lib/genealogy";

const DEFAULT_CENTER: [number, number] = [49.0, 31.0]; // Ukraine
const keyOf = (p: MapPoint) => `${p.latitude},${p.longitude}`;

/** The category with the most facts at a point decides its colour. */
function mainCategory(p: MapPoint): FactCategory {
  const counts = new Map<FactCategory, number>();
  for (const f of p.facts) {
    const c = factCategory(f.type);
    counts.set(c, (counts.get(c) ?? 0) + 1);
  }
  return [...counts.entries()].sort((x, y) => y[1] - x[1])[0]![0];
}

/** Places of birth, life, marriage, emigration and burial on an OpenStreetMap map. */
export default function MapPage() {
  const { t } = useTranslation();
  const { treeId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const personId = params.get("person");
  // From a place page: only that place, its facts listed.
  const placeId = params.get("place");
  const categories = parseCategories(params.get("cat"));
  const data = useMapData(treeId, personId);
  const [selected, setSelected] = useState<string | null>(null);

  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const layer = useRef<L.LayerGroup | null>(null);

  const set = (k: string, v: string | null) => {
    const next = new URLSearchParams(params);
    if (v) next.set(k, v);
    else next.delete(k);
    setParams(next, { replace: true });
    setSelected(null);
  };

  const catKey = categories.join(",");
  const points = useMemo(() => {
    const wanted = new Set(parseCategories(catKey));
    return (data.data?.points ?? [])
      .map((p) => ({
        ...p,
        facts: p.facts.filter(
          (f) =>
            (!wanted.size || wanted.has(factCategory(f.type))) &&
            (!placeId || f.place?.id === placeId),
        ),
      }))
      .filter((p) => p.facts.length > 0);
  }, [data.data, catKey, placeId]);

  // One person's life path: their places in chronological order.
  const path = useMemo(() => {
    if (!personId) return [];
    const stops = points
      .flatMap((p) => p.facts.map((f) => ({ p, sort: f.date?.year ?? Infinity })))
      .filter((x) => x.sort !== Infinity)
      .sort((x, y) => x.sort - y.sort)
      .map((x) => [Number(x.p.latitude), Number(x.p.longitude)] as [number, number]);
    return stops.filter((s, i) => i === 0 || s.join() !== stops[i - 1]!.join());
  }, [points, personId]);

  useEffect(() => {
    if (!el.current || map.current) return;
    const m = L.map(el.current).setView(DEFAULT_CENTER, 5);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "© OpenStreetMap",
    }).addTo(m);
    map.current = m;
    layer.current = L.layerGroup().addTo(m);
    return () => {
      m.remove();
      map.current = null;
      layer.current = null;
    };
  }, []);

  useEffect(() => {
    const m = map.current;
    const group = layer.current;
    if (!m || !group) return;
    group.clearLayers();
    if (path.length > 1) {
      L.polyline(path, { color: "#4d7c0f", weight: 3, dashArray: "6 6", opacity: 0.8 }).addTo(
        group,
      );
    }
    for (const p of points) {
      const color = CATEGORY_STYLE[mainCategory(p)].color;
      const marker = L.circleMarker([Number(p.latitude), Number(p.longitude)], {
        radius: Math.min(6 + p.facts.length * 2, 18),
        color: "#fff",
        weight: 2,
        fillColor: color,
        fillOpacity: 0.9,
      })
        .bindTooltip(`${p.label} (${p.facts.length})`)
        .on("click", () => setSelected(keyOf(p)));
      marker.addTo(group);
    }
    if (points.length) {
      const bounds = L.latLngBounds(points.map((p) => [Number(p.latitude), Number(p.longitude)]));
      m.fitBounds(bounds, { padding: [40, 40], maxZoom: 10 });
    }
  }, [points, path]);

  const current =
    points.find((p) => keyOf(p) === selected) ??
    (placeId && points.length === 1 ? points[0]! : null);
  const focus = (p: MapPoint) => {
    setSelected(keyOf(p));
    map.current?.setView([Number(p.latitude), Number(p.longitude)], 10);
  };

  return (
    <div className="mx-auto max-w-6xl space-y-4">
      <Link to={`/trees/${treeId}`} className="text-leaf-700 text-sm underline">
        ← {t("person.backToTree")}
      </Link>
      <PageHeader title={t("insights.map.title")} />
      <div className="flex flex-wrap items-center gap-3">
        <CategoryFilter value={categories} onChange={(v) => set("cat", v.join(",") || null)} />
        <PersonFilter
          treeId={treeId}
          personId={personId}
          label={t("insights.map.person")}
          onChange={(id) => set("person", id)}
        />
        {placeId && (
          <button
            type="button"
            className="bg-leaf-50 text-leaf-800 rounded-full px-3 py-1 text-xs"
            onClick={() => set("place", null)}
          >
            {t("places.mapFilter", { name: points[0]?.label ?? "…" })} ✕
          </button>
        )}
        {data.isFetching && <Spinner />}
      </div>
      <ErrorAlert error={data.error} />
      <div className="grid gap-4 lg:grid-cols-[1fr_22rem]">
        <div
          ref={el}
          className="border-bark-100 z-0 h-[60vh] min-h-80 rounded-lg border"
          aria-label={t("insights.map.title")}
        />
        <aside className="space-y-3 lg:max-h-[60vh] lg:overflow-y-auto">
          {current ? (
            <Card className="space-y-2">
              <div className="flex items-start justify-between gap-2">
                <h2 className="font-semibold">
                  {current.place_id ? (
                    <PlaceLink
                      treeId={treeId}
                      place={{ id: current.place_id, name: current.label }}
                    />
                  ) : (
                    current.label
                  )}
                </h2>
                <button
                  type="button"
                  className="text-bark-700 text-sm hover:underline"
                  onClick={() => setSelected(null)}
                >
                  {t("insights.map.allPlaces")}
                </button>
              </div>
              <ul className="space-y-2">
                {current.facts.map((f) => (
                  <li key={`${f.kind}-${f.id}`}>
                    <FactLine fact={f} treeId={treeId} />
                  </li>
                ))}
              </ul>
            </Card>
          ) : (
            <Card>
              <h2 className="mb-2 font-semibold">
                {t("insights.map.places", { count: points.length })}
              </h2>
              {points.length === 0 && data.data && (
                <p className="text-bark-700 text-sm">{t("insights.map.empty")}</p>
              )}
              <ul className="space-y-1">
                {points.map((p) => (
                  <li key={keyOf(p)}>
                    <button
                      type="button"
                      className="hover:bg-bark-50 flex w-full items-center gap-2 rounded px-1 py-0.5 text-left text-sm"
                      onClick={() => focus(p)}
                    >
                      <span
                        className="inline-block size-2.5 shrink-0 rounded-full"
                        style={{ background: CATEGORY_STYLE[mainCategory(p)].color }}
                      />
                      <span className="flex-1">{p.label}</span>
                      <span className="text-bark-700 tabular-nums">{p.facts.length}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </Card>
          )}
          {data.data && data.data.unplaced > 0 && (
            <Card className="space-y-1 text-sm">
              <p>{t("insights.map.unplaced", { count: data.data.unplaced })}</p>
              <p className="text-bark-700 text-xs">
                {data.data.places_without_coordinates.map((p) => p.name).join(", ")}
              </p>
            </Card>
          )}
        </aside>
      </div>
    </div>
  );
}
