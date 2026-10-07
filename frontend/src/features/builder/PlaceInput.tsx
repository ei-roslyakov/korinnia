import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import { Button, Dialog, ErrorAlert, Field, Input } from "@/components/ui";
import type { HistoricalName, Place, PlaceSummary } from "@/lib/genealogy";

import { useCreatePlace, usePlaceSearch } from "./api";
import { MapPicker, type LatLon } from "./MapPicker";

/** Place autocomplete (current + historical names, any script) with "create new place". */
export function PlaceInput({
  treeId,
  label,
  value,
  onChange,
}: {
  treeId: string;
  label: string;
  value: PlaceSummary | null;
  onChange: (p: PlaceSummary | null) => void;
}) {
  const { t } = useTranslation();
  const [text, setText] = useState("");
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const search = usePlaceSearch(treeId, text.trim());
  const results = open ? (search.data?.items ?? []) : [];

  if (value) {
    return (
      <div className="space-y-1">
        <span className="block text-sm font-medium">{label}</span>
        <div className="border-bark-100 bg-bark-50 flex items-center gap-2 rounded-md border px-3 py-2 text-sm">
          <span className="flex-1">
            {value.name}
            {value.country && <span className="text-bark-700"> ({value.country})</span>}
          </span>
          <button
            type="button"
            className="text-bark-700 hover:text-red-700"
            aria-label={t("builder.place.clear")}
            onClick={() => onChange(null)}
          >
            ✕
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="relative space-y-1">
      <label className="block text-sm font-medium">
        {label}
        <Input
          className="mt-1"
          role="combobox"
          aria-expanded={open}
          placeholder={t("builder.place.search")}
          value={text}
          onChange={(e) => {
            setText(e.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setTimeout(() => setOpen(false), 150)}
        />
      </label>
      {open && (
        <ul
          role="listbox"
          className="border-bark-100 bg-surface absolute z-30 mt-1 max-h-64 w-full overflow-y-auto rounded-md border py-1 shadow-lg"
        >
          {results.map((p) => (
            <li
              key={p.id}
              role="option"
              aria-selected={false}
              className="hover:bg-bark-100 cursor-pointer px-3 py-2 text-sm"
              onMouseDown={(e) => {
                e.preventDefault();
                onChange(p);
                setText("");
                setOpen(false);
              }}
            >
              <div>{p.name}</div>
              <div className="text-bark-700 text-xs">
                {[p.region, p.country, ...p.historical_names.map((h) => h.name)]
                  .filter(Boolean)
                  .join(" · ")}
              </div>
            </li>
          ))}
          <li
            role="option"
            aria-selected={false}
            className="text-leaf-700 hover:bg-bark-100 cursor-pointer px-3 py-2 text-sm font-medium"
            onMouseDown={(e) => {
              e.preventDefault();
              setCreating(true);
              setOpen(false);
            }}
          >
            +{" "}
            {text.trim()
              ? t("builder.place.createNamed", { name: text.trim() })
              : t("builder.place.create")}
          </li>
        </ul>
      )}
      {creating && (
        <PlaceDialog
          treeId={treeId}
          initialName={text.trim()}
          onClose={() => setCreating(false)}
          onCreated={(p) => {
            onChange(p);
            setText("");
            setCreating(false);
          }}
        />
      )}
    </div>
  );
}

export function PlaceDialog({
  treeId,
  initialName,
  onClose,
  onCreated,
}: {
  treeId: string;
  initialName: string;
  onClose: () => void;
  onCreated: (place: Place) => void;
}) {
  const { t } = useTranslation();
  const create = useCreatePlace(treeId);
  const [name, setName] = useState(initialName);
  const [region, setRegion] = useState("");
  const [country, setCountry] = useState("");
  const [pin, setPin] = useState<LatLon | null>(null);
  const [historical, setHistorical] = useState<HistoricalName[]>([]);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    e.stopPropagation();
    create.mutate(
      {
        name,
        region: region || null,
        country: country || null,
        latitude: pin ? String(pin.lat) : null,
        longitude: pin ? String(pin.lon) : null,
        historical_names: historical.filter((h) => h.name.trim()),
      },
      { onSuccess: onCreated },
    );
  };

  return (
    <Dialog open title={t("builder.place.newTitle")} onClose={onClose}>
      <form onSubmit={onSubmit} className="space-y-3">
        <Field label={t("builder.place.name")}>
          {(id) => (
            <Input
              id={id}
              required
              maxLength={300}
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          )}
        </Field>
        <div className="grid grid-cols-2 gap-3">
          <Field label={t("builder.place.region")}>
            {(id) => <Input id={id} value={region} onChange={(e) => setRegion(e.target.value)} />}
          </Field>
          <Field label={t("builder.place.country")}>
            {(id) => <Input id={id} value={country} onChange={(e) => setCountry(e.target.value)} />}
          </Field>
        </div>
        <div className="space-y-2">
          <span className="block text-sm font-medium">{t("builder.place.historical")}</span>
          {historical.map((h, i) => (
            <div key={i} className="flex gap-2">
              <Input
                aria-label={t("builder.place.historicalName")}
                placeholder={t("builder.place.historicalName")}
                value={h.name}
                onChange={(e) =>
                  setHistorical(
                    historical.map((x, j) => (j === i ? { ...x, name: e.target.value } : x)),
                  )
                }
              />
              <Input
                aria-label={t("builder.place.until")}
                placeholder={t("builder.place.until")}
                className="w-28"
                inputMode="numeric"
                value={h.until_year ?? ""}
                onChange={(e) =>
                  setHistorical(
                    historical.map((x, j) =>
                      j === i
                        ? { ...x, until_year: e.target.value ? Number(e.target.value) : null }
                        : x,
                    ),
                  )
                }
              />
              <Button
                variant="ghost"
                onClick={() => setHistorical(historical.filter((_, j) => j !== i))}
                aria-label={t("common.remove")}
              >
                ✕
              </Button>
            </div>
          ))}
          <Button variant="secondary" onClick={() => setHistorical([...historical, { name: "" }])}>
            + {t("builder.place.addHistorical")}
          </Button>
        </div>
        <MapPicker value={pin} onChange={setPin} height={220} />
        <ErrorAlert error={create.error} />
        <div className="flex justify-end gap-2">
          <Button variant="secondary" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button type="submit" busy={create.isPending}>
            {t("common.create")}
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
