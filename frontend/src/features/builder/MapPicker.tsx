import "leaflet/dist/leaflet.css";

import L from "leaflet";
import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

export interface LatLon {
  lat: number;
  lon: number;
}

const DEFAULT_CENTER: [number, number] = [49.0, 31.0]; // Ukraine

/** OpenStreetMap with a single pin; click to place / move it. */
export function MapPicker({
  value,
  onChange,
  height = 260,
}: {
  value: LatLon | null;
  onChange: (v: LatLon) => void;
  height?: number;
}) {
  const { t } = useTranslation();
  const el = useRef<HTMLDivElement>(null);
  const map = useRef<L.Map | null>(null);
  const marker = useRef<L.CircleMarker | null>(null);
  const onChangeRef = useRef(onChange);

  useEffect(() => {
    onChangeRef.current = onChange;
  }, [onChange]);

  useEffect(() => {
    if (!el.current || map.current) return;
    const m = L.map(el.current, { attributionControl: true }).setView(
      value ? [value.lat, value.lon] : DEFAULT_CENTER,
      value ? 10 : 5,
    );
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "© OpenStreetMap",
    }).addTo(m);
    m.on("click", (e: L.LeafletMouseEvent) =>
      onChangeRef.current({
        lat: Number(e.latlng.lat.toFixed(6)),
        lon: Number(e.latlng.lng.toFixed(6)),
      }),
    );
    map.current = m;
    return () => {
      m.remove();
      map.current = null;
      marker.current = null;
    };
    // The map is created once; later value changes only move the pin (below).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const m = map.current;
    if (!m) return;
    if (!value) {
      marker.current?.remove();
      marker.current = null;
      return;
    }
    if (marker.current) marker.current.setLatLng([value.lat, value.lon]);
    else {
      marker.current = L.circleMarker([value.lat, value.lon], {
        radius: 8,
        color: "#3f6212",
        fillColor: "#4d7c0f",
        fillOpacity: 0.8,
      }).addTo(m);
    }
  }, [value]);

  return (
    <div>
      <div
        ref={el}
        style={{ height }}
        className="border-bark-100 rounded-md border"
        data-testid="map-picker"
      />
      <p className="text-bark-700 mt-1 text-xs">{t("builder.map.hint")}</p>
    </div>
  );
}
