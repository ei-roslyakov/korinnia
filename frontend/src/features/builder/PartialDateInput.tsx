import { useId } from "react";
import { useTranslation } from "react-i18next";

import { Input, Select } from "@/components/ui";
import type { DatePrecision, PartialDateInput as Value } from "@/lib/genealogy";

const PRECISIONS: DatePrecision[] = [
  "unknown",
  "exact",
  "month",
  "year",
  "approx",
  "before",
  "after",
  "between",
];

const num = (s: string): number | null => (s.trim() === "" ? null : Number(s));

/** Editor for a genealogical partial date ("about 1850", "between 1914 and 1918", ...). */
export function PartialDateInput({
  label,
  value,
  onChange,
}: {
  label: string;
  value: Value | null;
  onChange: (v: Value | null) => void;
}) {
  const { t, i18n } = useTranslation();
  const id = useId();
  const v: Value = value ?? { precision: "unknown" };
  const p = v.precision ?? "unknown";
  const set = (patch: Partial<Value>) => onChange({ ...v, ...patch });
  const months = Array.from({ length: 12 }, (_, i) =>
    new Intl.DateTimeFormat(i18n.language, { month: "long", timeZone: "UTC" }).format(
      Date.UTC(2000, i, 1),
    ),
  );
  const showMonth = p !== "year" && p !== "unknown";
  const showDay = showMonth && p !== "month";

  const parts = (prefix: "" | "end_", aria: string) => (
    <div className="flex gap-2">
      <Input
        aria-label={`${aria}: ${t("builder.date.year")}`}
        className="w-24"
        inputMode="numeric"
        placeholder={t("builder.date.year")}
        value={v[`${prefix}year`] ?? ""}
        onChange={(e) => set({ [`${prefix}year`]: num(e.target.value) })}
      />
      {showMonth && (
        <Select
          aria-label={`${aria}: ${t("builder.date.month")}`}
          className="w-36"
          value={v[`${prefix}month`] ?? ""}
          onChange={(e) => set({ [`${prefix}month`]: num(e.target.value) })}
        >
          <option value="">{t("builder.date.month")}</option>
          {months.map((m, i) => (
            <option key={m} value={i + 1}>
              {m}
            </option>
          ))}
        </Select>
      )}
      {showDay && (
        <Input
          aria-label={`${aria}: ${t("builder.date.day")}`}
          className="w-20"
          inputMode="numeric"
          placeholder={t("builder.date.day")}
          value={v[`${prefix}day`] ?? ""}
          onChange={(e) => set({ [`${prefix}day`]: num(e.target.value) })}
        />
      )}
    </div>
  );

  return (
    <fieldset className="space-y-2">
      <legend className="text-sm font-medium" id={id}>
        {label}
      </legend>
      <div className="flex flex-wrap items-center gap-2">
        <Select
          aria-label={`${label}: ${t("builder.date.precision")}`}
          className="w-44"
          value={p}
          onChange={(e) => set({ precision: e.target.value as DatePrecision })}
        >
          {PRECISIONS.map((x) => (
            <option key={x} value={x}>
              {t(`builder.precision.${x}`)}
            </option>
          ))}
        </Select>
        {p !== "unknown" && parts("", label)}
        {p === "between" && (
          <>
            <span className="text-bark-700 text-sm">{t("builder.date.and")}</span>
            {parts("end_", `${label} (${t("builder.date.end")})`)}
          </>
        )}
      </div>
      <Input
        aria-label={`${label}: ${t("builder.date.phrase")}`}
        placeholder={t("builder.date.phrase")}
        value={v.phrase ?? ""}
        onChange={(e) => set({ phrase: e.target.value })}
      />
    </fieldset>
  );
}
