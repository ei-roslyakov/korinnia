import "leaflet/dist/leaflet.css";

import L from "leaflet";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router";

import { TextSkeleton } from "@/components/Skeleton";
import { Button, Card, Dialog, ErrorAlert, PageHeader } from "@/components/ui";
import { PlaceDialog, PlaceInput } from "@/features/builder/PlaceInput";
import { FactLine } from "@/features/insights/FactLine";
import { CATEGORY_STYLE, factTypeLabel } from "@/features/insights/facts";
import { Lightbox } from "@/features/media/Lightbox";
import { useTree } from "@/features/tree/api";
import {
  factCategory,
  type Fact,
  type PlacePage as Page,
  type PlaceSummary,
} from "@/lib/genealogy";
import { useToast } from "@/lib/toast";
import { atLeast } from "@/lib/types";

import { useMergePlace, usePlacePage } from "./api";
import { historicalLabel } from "./names";

// Sections in the order a life goes; other types follow in the order they first occur.
const TYPE_ORDER = ["birth", "baptism", "marriage", "partnership", "civil_union", "residence"];
const TYPE_LAST = ["death", "burial"];

function sections(facts: Fact[]): [string, Fact[]][] {
  const by = new Map<string, Fact[]>();
  for (const f of facts) by.set(f.type, [...(by.get(f.type) ?? []), f]);
  const rank = (type: string) => {
    if (TYPE_ORDER.includes(type)) return TYPE_ORDER.indexOf(type);
    if (TYPE_LAST.includes(type)) return 100 + TYPE_LAST.indexOf(type);
    return 50;
  };
  return [...by.entries()].sort((a, b) => rank(a[0]) - rank(b[0]));
}

/** A place's page: its names, who was born, lived, married, died or is buried there,
 * photos taken there and places nearby (D116). */
export function PlacePage() {
  const { t } = useTranslation();
  const { treeId = "", placeId = "" } = useParams();
  const tree = useTree(treeId);
  const page = usePlacePage(treeId, placeId);
  const [lightbox, setLightbox] = useState<number | null>(null);
  const [editing, setEditing] = useState(false);
  const [merging, setMerging] = useState(false);
  const canEdit = tree.data ? atLeast(tree.data.my_role, "editor") : false;
  const personLink = (id: string) => `/trees/${treeId}/people/${id}`;

  if (page.isPending) return <TextSkeleton lines={6} label={t("common.loading")} />;
  if (page.error) return <ErrorAlert error={page.error} />;
  const { place, facts, media, stories, nearby, persons } = page.data;
  const extra = [place.region, place.country].filter(Boolean).join(", ");

  return (
    <div className="mx-auto max-w-4xl space-y-4">
      <Link to={`/trees/${treeId}/places`} className="text-leaf-700 text-sm underline">
        ← {t("places.all")}
      </Link>
      <PageHeader
        title={place.name}
        actions={
          canEdit && (
            <>
              <Button variant="secondary" onClick={() => setEditing(true)}>
                {t("places.edit")}
              </Button>
              <Button variant="secondary" onClick={() => setMerging(true)}>
                {t("places.merge")}
              </Button>
            </>
          )
        }
      />
      <div className="text-bark-700 space-y-1 text-sm">
        {extra && <p>{extra}</p>}
        {place.historical_names.length > 0 && (
          <p data-testid="historical-names">
            {t("places.formerly")}{" "}
            {place.historical_names.map((h) => historicalLabel(t, h)).join(" · ")}
          </p>
        )}
        {place.notes && <p className="whitespace-pre-line">{place.notes}</p>}
        <p>
          {t("places.summary", { events: facts.length, people: persons.length })}
          {place.latitude && (
            <>
              {" · "}
              <Link
                to={`/trees/${treeId}/map?place=${place.id}`}
                className="text-leaf-700 underline"
              >
                {t("places.showOnMap")}
              </Link>
            </>
          )}
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-[1fr_18rem]">
        <div className="space-y-4">
          {facts.length === 0 && (
            <Card>
              <p className="text-bark-700 text-sm">{t("places.nothingHere")}</p>
            </Card>
          )}
          {sections(facts).map(([type, items]) => (
            <Card key={type} className="space-y-2">
              <h2 className="flex items-center gap-2 font-semibold">
                <span
                  className="inline-block size-2.5 rounded-full"
                  style={{ background: CATEGORY_STYLE[factCategory(type)].color }}
                />
                {factTypeLabel(t, type)}
                <span className="text-bark-700 text-sm font-normal">({items.length})</span>
              </h2>
              <ul className="space-y-1.5">
                {items.map((f) => (
                  <li key={`${f.kind}-${f.id}`}>
                    <FactLine fact={f} treeId={treeId} showType={false} showPlace={false} />
                  </li>
                ))}
              </ul>
            </Card>
          ))}
          {media.length > 0 && (
            <Card className="space-y-2">
              <h2 className="font-semibold">{t("places.photos")}</h2>
              <ul className="grid grid-cols-3 gap-2 sm:grid-cols-4">
                {media.map((m, i) => (
                  <li key={m.id}>
                    <button
                      type="button"
                      className="block w-full overflow-hidden rounded"
                      onClick={() => setLightbox(i)}
                    >
                      {m.urls.thumb ? (
                        <img
                          src={m.urls.thumb}
                          alt={m.title ?? m.original_filename}
                          loading="lazy"
                          className="aspect-square w-full object-cover"
                        />
                      ) : (
                        <span className="bg-bark-50 block aspect-square p-2 text-xs">
                          {m.title ?? m.original_filename}
                        </span>
                      )}
                    </button>
                  </li>
                ))}
              </ul>
            </Card>
          )}
          {stories.length > 0 && (
            <Card className="space-y-2">
              <h2 className="font-semibold">{t("places.stories")}</h2>
              <ul className="space-y-1 text-sm">
                {stories.map((s) => (
                  <li key={s.id}>
                    <Link
                      to={`/trees/${treeId}/stories/${s.id}`}
                      className="text-leaf-700 hover:underline"
                    >
                      {s.title}
                    </Link>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </div>
        <aside className="space-y-4">
          {place.latitude && place.longitude && <PlaceMap page={page.data} />}
          {nearby.length > 0 && (
            <Card className="space-y-2">
              <h2 className="font-semibold">{t("places.nearby")}</h2>
              <ul className="space-y-1 text-sm">
                {nearby.map((n) => (
                  <li key={n.place.id} className="flex justify-between gap-2">
                    <Link
                      to={`/trees/${treeId}/places/${n.place.id}`}
                      className="text-leaf-700 hover:underline"
                    >
                      {n.place.name}
                    </Link>
                    <span className="text-bark-700 tabular-nums">
                      {t("places.km", { km: Math.round(n.distance_km) })}
                    </span>
                  </li>
                ))}
              </ul>
            </Card>
          )}
        </aside>
      </div>

      {lightbox !== null && (
        <Lightbox
          items={media}
          index={lightbox}
          onIndex={setLightbox}
          onClose={() => setLightbox(null)}
          personLink={personLink}
          comments={tree.data ? { treeId, role: tree.data.my_role } : undefined}
        />
      )}
      {editing && (
        <PlaceDialog
          treeId={treeId}
          place={place}
          onClose={() => setEditing(false)}
          onCreated={() => setEditing(false)}
        />
      )}
      {merging && <MergeDialog treeId={treeId} source={place} onClose={() => setMerging(false)} />}
    </div>
  );
}

/** Centred on the place; precise spots (e.g. graves) of its facts and nearby places too. */
function PlaceMap({ page }: { page: Page }) {
  const { t } = useTranslation();
  const el = useRef<HTMLDivElement>(null);
  const { place, facts, nearby } = page;

  useEffect(() => {
    if (!el.current) return;
    const center: [number, number] = [Number(place.latitude), Number(place.longitude)];
    const m = L.map(el.current, { scrollWheelZoom: false }).setView(center, 11);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "© OpenStreetMap",
    }).addTo(m);
    const dot = (at: [number, number], color: string, radius: number, label: string) =>
      L.circleMarker(at, { radius, color: "#fff", weight: 2, fillColor: color, fillOpacity: 0.9 })
        .bindTooltip(label)
        .addTo(m);
    for (const n of nearby) {
      if (n.place.latitude && n.place.longitude) {
        dot([Number(n.place.latitude), Number(n.place.longitude)], "#a8a29e", 5, n.place.name);
      }
    }
    dot(center, "#4d7c0f", 9, place.name);
    for (const f of facts) {
      if (f.latitude && f.longitude) {
        const names = f.persons.map((p) => p.display_name).join(", ");
        dot(
          [Number(f.latitude), Number(f.longitude)],
          CATEGORY_STYLE[factCategory(f.type)].color,
          6,
          `${f.cemetery_name ?? factTypeLabel(t, f.type)}: ${names}`,
        );
      }
    }
    return () => {
      m.remove();
    };
  }, [place, facts, nearby, t]);

  return (
    <div
      ref={el}
      className="border-bark-100 z-0 h-56 rounded-lg border"
      aria-label={t("places.mapLabel", { name: place.name })}
    />
  );
}

function MergeDialog({
  treeId,
  source,
  onClose,
}: {
  treeId: string;
  source: PlaceSummary;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const toast = useToast();
  const merge = useMergePlace(treeId, source.id);
  const [target, setTarget] = useState<PlaceSummary | null>(null);
  const same = target?.id === source.id;

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!target || same) return;
    merge.mutate(target.id, {
      onSuccess: (merged) => {
        toast(t("places.merged", { source: source.name, target: merged.name }));
        void navigate(`/trees/${treeId}/places/${merged.id}`, { replace: true });
      },
    });
  };

  return (
    <Dialog open title={t("places.mergeTitle", { name: source.name })} onClose={onClose}>
      <form onSubmit={onSubmit} className="space-y-3 text-sm">
        <p className="text-bark-700">{t("places.mergeHint")}</p>
        <PlaceInput
          treeId={treeId}
          label={t("places.mergeInto")}
          value={target}
          onChange={setTarget}
        />
        {same && <p className="text-red-700">{t("places.mergeSelf")}</p>}
        <ErrorAlert error={merge.error} />
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button type="submit" busy={merge.isPending} disabled={!target || same}>
            {t("places.mergeButton")}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
